from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.core.spec_schema import CopilotSpec
from app.core.generators.pyspark_gen import render_pyspark_job_v2
from app.core.generators.dag_gen import render_airflow_dag_v2
from app.core.generators.spark_conf_gen import render_spark_conf_v2
from app.core.workspace.materialize import materialize_files
from app.core.git_ops.repo_manager import ensure_repo, commit_all, read_baseline, write_baseline
from app.core.build_registry import BuildRegistry
from app.core.build_plan.persist import save_plan, append_events
from app.core.policy import DEFAULT_POLICY_ENGINE

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"
SPEC_PATH = PROJECT_ROOT / "copilot_spec.yaml"


def _merge_files(dst: Dict[str, str], src: Any) -> None:
    if not src:
        return
    if not isinstance(src, dict):
        raise TypeError(f"Expected generator output as Dict[path,str], got: {type(src)}")
    for k, v in src.items():
        dst[str(k)] = str(v)


def _finalize_baseline(workspace_job_dir: Path) -> str:
    """
    In tests / constrained envs, git may be unavailable. Fall back to a stable baseline marker
    instead of failing the entire build intent path.
    """
    baseline = None
    try:
        ensure_repo(workspace_job_dir)
        baseline = read_baseline(workspace_job_dir)
        if baseline:
            return baseline

        commit_all(workspace_job_dir, "copilot: baseline")

        write_baseline(workspace_job_dir, "PENDING")
        commit_all(workspace_job_dir, "copilot: baseline snapshot")

        baseline_commit = commit_all(workspace_job_dir, "copilot: baseline snapshot (finalize)")
        write_baseline(workspace_job_dir, baseline_commit)
        return baseline_commit

    except Exception:
        # fallback baseline (keeps contract: baseline_commit is a string)
        fallback = baseline or "NO_GIT_BASELINE"
        try:
            write_baseline(workspace_job_dir, fallback)
        except Exception:
            pass
        return fallback


def _finding_to_dict(f: Any) -> Dict[str, Any]:
    if f is None:
        return {}
    if isinstance(f, dict):
        return f
    d = getattr(f, "__dict__", None)
    if isinstance(d, dict):
        return d
    return dict(f)


def _ms(start: float, end: float) -> int:
    return int(round((end - start) * 1000))


def build_v2_from_spec(
    spec: CopilotSpec,
    write_spec_yaml: bool = True,
    job_name_override: Optional[str] = None,
    confidence: Optional[float] = None,
    options: Optional[Dict[str, Any]] = None,   # ✅ Stage2
    advisors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from app.core.build_plan.planner import make_build_plan
    from app.core.build_plan.advisors import run_plan_advisors
    from app.core.build_plan.runner import PlanRunner
    from app.core.build_plan.events import BuildEvent

    t0_total = time.perf_counter()

    options = options or {}
    policy_results = []

    advisors = advisors or {}
    advisors = {**advisors, **(options.get("advisors") or {})}

    resolved_job_name = (job_name_override or spec.job_name).strip()
    if resolved_job_name != spec.job_name:
        spec = spec.model_copy(update={"job_name": resolved_job_name})

    registry = BuildRegistry(WORKSPACE_ROOT, spec.job_name)
    spec_hash = registry.compute_spec_hash(spec)

    # BuildEvent list that will be appended at the end (or earlier on error paths)
    events = [BuildEvent.mk("BuildRequested", spec.job_name, spec_hash).__dict__]
    events.append(BuildEvent.mk("SpecValidated", spec.job_name, spec_hash).__dict__)

    # -------------------------
    # SKIP PATH
    # -------------------------
    if not registry.should_rebuild(spec_hash):
        t0_skip = time.perf_counter()

        workspace_job_dir = WORKSPACE_ROOT / spec.job_name
        workspace_job_dir.mkdir(parents=True, exist_ok=True)

        baseline_ref = (
            read_baseline(workspace_job_dir)
            if workspace_job_dir.exists()
            else None
        ) or options.get("base_ref") or "upstream/main"

        # advisors resolved even for skip (so fingerprint stays consistent)
        t0_plan = time.perf_counter()
        tmp_plan = make_build_plan(
            job_name=spec.job_name,
            spec_hash=spec_hash,
            baseline_ref=baseline_ref,
            expected_files=[],
            plugin_fingerprint="core",
            advisor_fingerprint="core",
        )
        t1_plan = time.perf_counter()
        events.append(BuildEvent.mk(
            "StepCompleted",
            spec.job_name,
            spec_hash,
            step_id="plan_created_skip",
            payload={"duration_ms": _ms(t0_plan, t1_plan)},
        ).__dict__)

        # policy evaluation timing
        t0_pol = time.perf_counter()
        policy_ctx = {
            "spec": spec.model_dump(),
            "plan": tmp_plan,
            "workspace_head": None,
            "upstream_head": None,
        }
        policy_results = DEFAULT_POLICY_ENGINE.evaluate(policy_ctx)
        t1_pol = time.perf_counter()
        events.append(BuildEvent.mk(
            "StepCompleted",
            spec.job_name,
            spec_hash,
            step_id="policy_evaluate_skip",
            payload={"duration_ms": _ms(t0_pol, t1_pol), "result_count": len(policy_results)},
        ).__dict__)

        if DEFAULT_POLICY_ENGINE.is_blocking(policy_results):
            events.append(BuildEvent.mk(
                "StepFailed",
                spec.job_name,
                spec_hash,
                step_id="policy_gate_skip",
                payload={
                    "duration_ms": _ms(t0_pol, t1_pol),
                    "result_count": len(policy_results),
                },
            ).__dict__)
            append_events(workspace_job_dir, events)
            return {
                "message": "Policy check failed",
                "job_name": spec.job_name,
                "spec_hash": spec_hash,
                "policy_results": [r.__dict__ for r in policy_results],
                "skipped": True,
            }

        # advisors timing
        t0_adv = time.perf_counter()
        adv = run_plan_advisors(tmp_plan, advisors=advisors, project_root=PROJECT_ROOT, options=options)
        t1_adv = time.perf_counter()
        events.append(BuildEvent.mk(
            "StepCompleted",
            spec.job_name,
            spec_hash,
            step_id="advisors_run_skip",
            payload={"duration_ms": _ms(t0_adv, t1_adv), "finding_count": len(adv.findings or [])},
        ).__dict__)

        plan = adv.plan
        plan_id = save_plan(workspace_job_dir, plan)

        runner = PlanRunner(WORKSPACE_ROOT)
        res = runner.run(
            plan=plan,
            registry=registry,
            workspace_job_dir=workspace_job_dir,
            generated_files={},
            baseline_commit=baseline_ref,
            skipped=True,
            advisor_findings=[_finding_to_dict(f) for f in (adv.findings or [])],
            confidence=confidence,
        )

        t1_skip = time.perf_counter()
        events.append(BuildEvent.mk(
            "StepCompleted",
            spec.job_name,
            spec_hash,
            step_id="build_v2_total_skip",
            payload={"duration_ms": _ms(t0_skip, t1_skip)},
        ).__dict__)
        events.append(BuildEvent.mk(
            "StepCompleted",
            spec.job_name,
            spec_hash,
            step_id="build_v2_total",
            payload={"duration_ms": _ms(t0_total, t1_skip)},
        ).__dict__)

        append_events(workspace_job_dir, events + res.events)

        return {
            "message": "No changes detected. Skipping rebuild.",
            "job_name": spec.job_name,
            "spec_hash": spec_hash,
            "skipped": True,
            "plan_id": plan_id,
            "events": events + res.events,
            "advisor_findings": res.advisor_findings,
            "confidence": confidence,
            "policy_results": [r.__dict__ for r in policy_results],
        }

    # -------------------------
    # BUILD PATH
    # -------------------------
    t0_build = time.perf_counter()
    generated_files: Dict[str, str] = {}

    # generation timing
    t0_gen = time.perf_counter()
    if spec.language.lower() == "pyspark":
        _merge_files(generated_files, render_pyspark_job_v2(spec))
    elif spec.language.lower() == "scala":
        raise ValueError("Scala generator not wired yet (language='scala').")
    else:
        raise ValueError(f"Unsupported language: {spec.language}")

    _merge_files(generated_files, render_airflow_dag_v2(spec))

    spark_conf_obj = render_spark_conf_v2(spec)
    if isinstance(spark_conf_obj, str):
        spark_conf_json = spark_conf_obj
    elif isinstance(spark_conf_obj, dict):
        spark_conf_json = json.dumps(spark_conf_obj, indent=2, sort_keys=True)
    else:
        raise TypeError(f"Spark conf must be dict or JSON string, got: {type(spark_conf_obj)}")

    generated_files["configs/spark_conf_default.json"] = spark_conf_json
    t1_gen = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="generate_artifacts",
        payload={"duration_ms": _ms(t0_gen, t1_gen), "file_count": len(generated_files)},
    ).__dict__)

    if write_spec_yaml:
        SPEC_PATH.write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False), encoding="utf-8")

    workspace_job_dir = WORKSPACE_ROOT / spec.job_name

    # materialize timing
    t0_mat = time.perf_counter()
    materialize_files(workspace_job_dir, generated_files)
    t1_mat = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="materialize_workspace",
        payload={"duration_ms": _ms(t0_mat, t1_mat), "file_count": len(generated_files)},
    ).__dict__)

    # baseline timing
    t0_base = time.perf_counter()
    baseline_commit = _finalize_baseline(workspace_job_dir)
    t1_base = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="finalize_baseline",
        payload={"duration_ms": _ms(t0_base, t1_base), "baseline_commit": baseline_commit},
    ).__dict__)

    # build plan BEFORE advisors (so advisors can mutate metadata; fingerprints updated)
    t0_plan2 = time.perf_counter()
    tmp_plan = make_build_plan(
        job_name=spec.job_name,
        spec_hash=spec_hash,
        baseline_ref=baseline_commit,
        expected_files=list(generated_files.keys()),
        plugin_fingerprint="core",
        advisor_fingerprint="core",
    )
    t1_plan2 = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="plan_created",
        payload={"duration_ms": _ms(t0_plan2, t1_plan2)},
    ).__dict__)

    # policy evaluation timing
    t0_pol2 = time.perf_counter()
    policy_ctx = {
        "spec": spec.model_dump(),
        "plan": tmp_plan,
        "workspace_head": None,
        "upstream_head": None,
    }
    policy_results = DEFAULT_POLICY_ENGINE.evaluate(policy_ctx)
    t1_pol2 = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="policy_evaluate",
        payload={"duration_ms": _ms(t0_pol2, t1_pol2), "result_count": len(policy_results)},
    ).__dict__)

    if DEFAULT_POLICY_ENGINE.is_blocking(policy_results):
        events.append(BuildEvent.mk(
            "StepFailed",
            spec.job_name,
            spec_hash,
            step_id="policy_gate",
            payload={
                "duration_ms": _ms(t0_pol2, t1_pol2),
                "blocking": True,
            },
        ).__dict__)
        append_events(workspace_job_dir, events)
        return {
            "message": "Policy check failed",
            "job_name": spec.job_name,
            "spec_hash": spec_hash,
            "policy_results": [r.__dict__ for r in policy_results],
            "skipped": True,
        }

    # advisors timing
    t0_adv2 = time.perf_counter()
    adv = run_plan_advisors(tmp_plan, advisors=advisors, project_root=PROJECT_ROOT, options=options)
    t1_adv2 = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="advisors_run",
        payload={
            "duration_ms": _ms(t0_adv2, t1_adv2),
            "finding_count": len(adv.findings or []),
        },
    ).__dict__)

    plan = adv.plan
    plan_id = save_plan(workspace_job_dir, plan)

    runner = PlanRunner(WORKSPACE_ROOT)

    # runner timing
    t0_run = time.perf_counter()

    res = runner.run(
        plan=plan,
        registry=registry,
        workspace_job_dir=workspace_job_dir,
        generated_files=generated_files,
        baseline_commit=baseline_commit,
        skipped=False,
        advisor_findings=[_finding_to_dict(f) for f in (adv.findings or [])],
        confidence=confidence,
    )

    t1_run = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="plan_runner_execute",
        payload={
            "duration_ms": _ms(t0_run, t1_run),
            "skipped": False,
        },
    ).__dict__)

    t1_build = time.perf_counter()
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="build_v2_total_build",
        payload={"duration_ms": _ms(t0_build, t1_build)},
    ).__dict__)
    events.append(BuildEvent.mk(
        "StepCompleted",
        spec.job_name,
        spec_hash,
        step_id="build_v2_total",
        payload={"duration_ms": _ms(t0_total, t1_build)},
    ).__dict__)

    append_events(workspace_job_dir, events + res.events)

    return {
        "message": "Build V2 completed",
        "job_name": spec.job_name,
        "workspace_dir": str(workspace_job_dir),
        "files": list(generated_files.keys()),
        "baseline_commit": baseline_commit,
        "spec_hash": spec_hash,
        "skipped": False,
        "plan_id": plan_id,
        "events": events + res.events,
        "advisor_findings": res.advisor_findings,
        "confidence": confidence,
        "policy_results": [r.__dict__ for r in policy_results],
    }
