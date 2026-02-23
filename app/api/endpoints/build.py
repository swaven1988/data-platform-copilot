from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, List

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.endpoints.build_v2_impl import build_v2_from_spec
from app.core.git_ops.repo_manager import (
    commit_all,
    ensure_repo,
    read_baseline,
    write_baseline,
)
from app.core.packaging.packager import make_zip
from app.core.project_analyzer.intent_parser import parse_requirement_to_spec
from app.core.spec_schema import BuildV2Request, CopilotSpec
from app.core.workspace.materialize import materialize_files
from app.core.build_registry import BuildRegistry

# V1 generator surface (stable names)
from app.core.generators.pyspark_gen import render_pyspark_job
from app.core.generators.dag_gen import render_airflow_dag
from app.core.generators.spark_conf_gen import render_spark_conf

from app.plugins.advisors._internal.registry import PluginRegistry
from app.plugins.advisors._internal.config import AdvisorsRunConfig
from app.core.intelligence.engine_facade import IntelligenceFacade

from app.api.models.build_responses import (
    BuildV2Response,
    BuildIntentDryRunResponse,
    BuildIntentBuildResponse,
)
from app.api.models.build_responses import BuildV2Response

from datetime import datetime



router = APIRouter(prefix="/build", tags=["Build"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"
SPEC_PATH = PROJECT_ROOT / "copilot_spec.yaml"


@router.get("/history")
def build_history(job_name: str):
    registry = BuildRegistry(WORKSPACE_ROOT, job_name)
    meta = registry.load()
    return {
        "job_name": job_name,
        "current_build_id": meta.get("current_build_id"),
        "builds": meta.get("builds", []),
    }


def _merge_files(dst: Dict[str, str], maybe_files: Any) -> None:
    """
    Generators should return Dict[path, content].
    """
    if maybe_files is None:
        return

    if isinstance(maybe_files, dict):
        for k, v in maybe_files.items():
            dst[str(k)] = str(v)
        return

    raise TypeError(f"Expected generator output as Dict[path,str], got: {type(maybe_files)}")


def _spark_conf_to_json(maybe_conf: Any) -> str:
    """
    spark_conf generator can return:
      - dict -> json.dumps
      - str  -> already JSON
    """
    if isinstance(maybe_conf, str):
        return maybe_conf
    if isinstance(maybe_conf, dict):
        return json.dumps(maybe_conf, indent=2, sort_keys=True)
    raise TypeError(f"Expected spark conf as dict or str, got: {type(maybe_conf)}")


def _finalize_workspace_repo(workspace_job_dir: Path) -> str:
    """
    Stage-1 baseline semantics (idempotent).
    """
    ensure_repo(workspace_job_dir)

    baseline = read_baseline(workspace_job_dir)
    if baseline:
        return baseline

    commit_all(workspace_job_dir, "copilot: baseline")

    write_baseline(workspace_job_dir, "PENDING")
    commit_all(workspace_job_dir, "copilot: baseline snapshot")

    baseline_commit = commit_all(workspace_job_dir, "copilot: get snapshot head")

    write_baseline(workspace_job_dir, baseline_commit)
    baseline_commit = commit_all(workspace_job_dir, "copilot: baseline snapshot (finalize)")

    write_baseline(workspace_job_dir, baseline_commit)
    return baseline_commit

def _build_intent_plan_preview(spec_obj: Any, base_ref: str) -> Dict[str, Any]:
    job_name = getattr(spec_obj, "job_name", None) or getattr(spec_obj, "name", None) or "example_pipeline"
    language = getattr(spec_obj, "language", None) or "pyspark"

    expected_files: List[str] = []
    if language == "pyspark":
        expected_files = [
            f"jobs/pyspark/src/{job_name}.py",
            f"dags/{job_name}_pipeline.py",
            "configs/spark_conf_default.json",
        ]

    return {
        "baseline_ref": base_ref or "upstream/main",
        "expected_files": expected_files,
        "job_name": job_name,
        "language": language,
        "kind": "intent_preview",
    }

@router.get("/build/{job_name}/runtime")
def get_build_runtime(job_name: str):
    """
    Returns runtime metadata for the latest build of a job.
    """
    workspace_root = Path(__file__).resolve().parents[3] / "workspace"
    job_dir = workspace_root / job_name
    meta_file = job_dir / ".copilot_meta.json"

    if not meta_file.exists():
        return {
            "job_name": job_name,
            "message": "No build metadata found",
        }

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    current_id = meta.get("current_build_id")

    if not current_id:
        return {
            "job_name": job_name,
            "message": "No builds registered yet",
        }

    builds = meta.get("builds", [])
    current_build = next((b for b in builds if b.get("build_id") == current_id), None)

    return {
        "job_name": job_name,
        "current_build_id": current_id,
        "build": current_build,
    }

# ----------------------------
# Build (V1): YAML-driven (copilot_spec.yaml)
# ----------------------------
@router.post("/")
def build_pipeline(
    base_ref: str = Query("upstream/main"),
    include_intelligence: bool = Query(True),
):
    try:
        if not SPEC_PATH.exists():
            raise FileNotFoundError(f"Spec file not found at: {SPEC_PATH}")

        with SPEC_PATH.open("r", encoding="utf-8") as f:
            spec_dict = yaml.safe_load(f) or {}

        spec = CopilotSpec(**spec_dict)

        generated_files: Dict[str, str] = {}

        if spec.language.lower() == "pyspark":
            _merge_files(generated_files, render_pyspark_job(spec))
        elif spec.language.lower() == "scala":
            raise ValueError("Scala generator not wired yet (language='scala').")
        else:
            raise ValueError(f"Unsupported language: {spec.language}")

        _merge_files(generated_files, render_airflow_dag(spec))

        spark_conf = render_spark_conf(spec)
        generated_files["configs/spark_conf_default.json"] = _spark_conf_to_json(spark_conf)

        zip_path = make_zip(spec.job_name, generated_files)

        workspace_job_dir = WORKSPACE_ROOT / spec.job_name
        materialize_files(workspace_job_dir, generated_files)

        baseline_commit = _finalize_workspace_repo(workspace_job_dir)

        resp = {
            "message": "Generated project artifacts successfully (Build V1)",
            "job_name": spec.job_name,
            "language": spec.language,
            "dq_enabled": getattr(spec, "dq_enabled", False),
            "spec_path": str(SPEC_PATH),
            "zip_path": zip_path,
            "files": list(generated_files.keys()),
            "workspace_dir": str(workspace_job_dir),
            "baseline_commit": baseline_commit,
        }

        if include_intelligence:
            resp = IntelligenceFacade.analyze_and_inject(resp, base_ref=base_ref)

        return resp

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------
# Build V2: UI-driven (JSON payload)
# ----------------------------
# 2) Update signature + inject inside /v2 endpoint EXACTLY like below

@router.post("/v2")
def build_pipeline_v2(
    req: BuildV2Request,
    contract_hash: str = Query(...),
    base_ref: str = Query("upstream/main"),
    include_intelligence: bool = Query(True),
):
    try:
        build_result = build_v2_from_spec(
            spec=req.spec,
            write_spec_yaml=req.write_spec_yaml,
            job_name_override=req.job_name_override,
            contract_hash=contract_hash,
        )

        if include_intelligence:
            build_result = IntelligenceFacade.analyze_and_inject(build_result, base_ref=base_ref, contract_hash=contract_hash)

        return build_result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------
# Build Intent: Requirement -> Parsed Spec -> Reuse Build V2 pipeline
# ----------------------------
class BuildIntentRequest(BaseModel):
    requirement: str = Field(..., min_length=3)
    job_name_hint: Optional[str] = None
    defaults: Dict[str, Any] = Field(default_factory=dict)
    write_spec_yaml: bool = True
    dry_run: bool = False
    explain: bool = False
    options: Dict[str, Any] = Field(default_factory=dict)
    advisors: Dict[str, Any] = Field(default_factory=dict) 
    force: bool = False 


@router.post("/intent")
def build_from_intent(req: BuildIntentRequest):
    try:
        parsed = parse_requirement_to_spec(
            requirement=req.requirement,
            job_name_hint=req.job_name_hint,
            defaults=req.defaults or {},
        )

        spec_obj = CopilotSpec(**(parsed.spec or {}))

        # ---- normalize spec from request inputs (must happen BEFORE guardrails) ----
        # 1) Ensure job_name is present (parser may not set it for synthetic requirements)
        if (not getattr(spec_obj, "job_name", None)) and req.job_name_hint:
            spec_obj = spec_obj.model_copy(update={"job_name": req.job_name_hint})

        # 2) Apply defaults only to missing/empty fields (tests rely on this)
        if req.defaults:
            cur = spec_obj.model_dump()
            patch = {
                k: v
                for k, v in (req.defaults or {}).items()
                if cur.get(k) in (None, "", [], {})
            }
            if patch:
                spec_obj = spec_obj.model_copy(update=patch)
        # -------------------------------------------------------------------------


        # Guardrails
        if not spec_obj.source_table or "." not in spec_obj.source_table:
            raise HTTPException(status_code=400, detail="Invalid source_table format. Expected <db>.<table>")
        if not spec_obj.target_table or "." not in spec_obj.target_table:
            raise HTTPException(status_code=400, detail="Invalid target_table format. Expected <db>.<table>")
        if spec_obj.write_mode not in {"merge", "append", "overwrite"}:
            raise HTTPException(status_code=400, detail=f"Unsupported write_mode: {spec_obj.write_mode}")
        if spec_obj.language not in {"pyspark", "scala"}:
            raise HTTPException(status_code=400, detail=f"Unsupported language: {spec_obj.language}")

        registry = BuildRegistry(WORKSPACE_ROOT, spec_obj.job_name)
        spec_hash = registry.compute_spec_hash(spec_obj)
        warnings_out = [w.__dict__ for w in (parsed.warnings or [])]

        # Load plugin registry once
        reg = PluginRegistry(PROJECT_ROOT / "app" / "plugins" / "advisors")
        reg.load_all()
        plugin_fingerprint = reg.fingerprint

        base_ref = (req.options or {}).get("base_ref") or "upstream/main"
        include_intelligence = (req.options or {}).get("include_intelligence", True)

        expected_files: List[str] = []
        if spec_obj.language == "pyspark":
            expected_files = [
                f"jobs/pyspark/src/{spec_obj.job_name}.py",
                f"dags/{spec_obj.job_name}_pipeline.py",
                "configs/spark_conf_default.json",
            ]

        # Single context object used everywhere (advisors + build)
        ctx: Dict[str, Any] = {
            "spec": spec_obj.model_dump(),
            "baseline_ref": base_ref,
            "expected_files": expected_files,
            "plan": {
                "baseline_ref": base_ref,
                "expected_files": expected_files,
                "job_name": spec_obj.job_name,
                "language": spec_obj.language,
                "kind": "intent_preview",
            },
            "workspace_head": None,
            "upstream_head": None,
        }

        # -------------------------
        # DRY RUN
        # -------------------------
        if req.dry_run:
            from app.core.build_plan.models import BuildPlan

            advisors_cfg = req.advisors or {}

            cfg = AdvisorsRunConfig(
                enabled=advisors_cfg.get("enabled"),
                disabled=advisors_cfg.get("disabled", []),
                options=(advisors_cfg.get("options") or {}),   # per-plugin options only
                force=bool(advisors_cfg.get("force", False) or req.force),
            )

            plan = BuildPlan(
                plan_version="intent-v0",
                spec_hash=spec_hash,
                job_name=spec_obj.job_name,
                baseline_ref=base_ref,
                plugin_fingerprint=plugin_fingerprint,
                steps=[],
                expected_files=expected_files,
                metadata={},
            )

            ctx["plan"] = plan  # override preview dict with real plan model for advisors

            advisor_findings = reg.run(context=ctx, cfg=cfg) or []
            advisor_findings_out = [getattr(f, "__dict__", f) for f in advisor_findings]

            resp = {
                "message": "Parsed requirement (dry run)",
                "parsed_spec": spec_obj.model_dump(),
                "warnings": warnings_out,
                "spec_hash": spec_hash,
                "confidence": getattr(parsed, "confidence", None),
                "plugin_fingerprint": plugin_fingerprint,
                "advisor_findings": advisor_findings_out,
            }

            if req.explain and hasattr(parsed, "explain"):
                resp["explain"] = parsed.explain

            if include_intelligence:
                resp = IntelligenceFacade.analyze_and_inject(resp, base_ref=base_ref)

            return BuildIntentDryRunResponse(**resp).model_dump()


        # -------------------------
        # PLAN ONLY
        # -------------------------
        if bool(req.options.get("plan_only")):
            resp = {
                "message": "Plan only (no build executed)",
                "spec": spec_obj.model_dump(),
                "spec_hash": spec_hash,
                "will_rebuild": registry.should_rebuild(spec_hash),
            }

            if include_intelligence:
                resp = IntelligenceFacade.analyze_and_inject(resp, base_ref=base_ref)

            return resp

        # -------------------------
        # BUILD
        # -------------------------
        if not req.options.get("contract_hash"):
            raise HTTPException(
                status_code=400,
                detail="contract_hash required for intent build"
            )

        build_result = build_v2_from_spec(
            spec=spec_obj,
            write_spec_yaml=req.write_spec_yaml,
            job_name_override=None,
            contract_hash=req.options.get("contract_hash"),  # 🔒 ENFORCED
            options={
                **(req.options or {}),
                "base_ref": base_ref,
                "include_intelligence": include_intelligence,
                "advisors": {**(req.advisors or {}), "force": req.force},
            },
        )


        advisor_findings_out = build_result.get("advisor_findings", []) or []
        plugin_fingerprint_out = build_result.get("plugin_fingerprint") or plugin_fingerprint

        resp = {
            "message": "Build completed from requirement",
            "parsed_spec": spec_obj.model_dump(),
            "warnings": warnings_out,
            "spec_hash": spec_hash,
            "build_result": build_result,
            "confidence": getattr(parsed, "confidence", None),
            "plugin_fingerprint": plugin_fingerprint_out,
            "advisor_findings": advisor_findings_out,
        }

        if req.explain and hasattr(parsed, "explain"):
            resp["explain"] = parsed.explain

        if include_intelligence:
            resp = IntelligenceFacade.analyze_and_inject(resp, base_ref=base_ref)

        return BuildIntentBuildResponse(**resp).model_dump()

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




