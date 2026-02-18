import os
import time
import json
import requests
from pathlib import Path
import streamlit as st
from typing import Optional, Dict, Any
from textwrap import dedent

# ----------------------------
# Config
# ----------------------------
try:
    API_URL = st.secrets["API_URL"]
except Exception:
    API_URL = "http://localhost:8001"

API_URL = (API_URL or "").rstrip("/")

st.set_page_config(page_title="Data Platform Copilot", layout="wide")
st.title("🧠 Data Platform Copilot")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

INTENT_DSL_TEMPLATE = dedent(
    """
    # Title: Example - Add /build/intent (deterministic)

    ## Target
    repo: data-platform-copilot
    ref: main
    paths: ui,app,copilot_spec.yaml

    ## Requirements
    - Implement /build/intent to parse deterministic requirement into an IntentSpec
    - Compile IntentSpec into build_v2 plan and execute build_v2
    - Return intent_spec + build_plan + build_id

    ## Acceptance Criteria
    - /build/intent accepts DSL + YAML + JSON
    - Validation errors return field pointers
    - build_v2 is reused (no duplicate builder)

    ## Outputs
    - api: /build/intent
    - tests: tests/test_build_intent_parser.py
    """
).strip()

# Public presets (keep names generic for open-source)
PRESET_DEFAULTS: dict[str, dict[str, Any]] = {
    "generic": {
        "tags": ["copilot", "dev"],
        "spark_conf_overrides": {},
    },
    "enterprise_a": {
        "tags": ["copilot", "enterprise"],
        "spark_conf_overrides": {
            "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
        },
    },
    "enterprise_b": {
        "tags": ["copilot", "enterprise"],
        "spark_conf_overrides": {
            "spark.sql.adaptive.skewJoin.enabled": "true",
        },
    },
}

# ----------------------------
# Helpers
# ----------------------------
def list_workspace_jobs() -> list[str]:
    if not WORKSPACE_ROOT.exists():
        return []
    return sorted([p.name for p in WORKSPACE_ROOT.iterdir() if p.is_dir()])


def _raise_for_status_with_body(resp: requests.Response) -> None:
    """
    Raise HTTPError but keep body for nicer UI display.
    """
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # attach response for later
        raise e


def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = requests.get(f"{API_URL}{path}", params=params, timeout=30)
    _raise_for_status_with_body(resp)
    return resp.json()


def api_post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
    _raise_for_status_with_body(resp)
    return resp.json()


def show_http_error(e: requests.HTTPError) -> None:
    """
    Attempt to show server JSON error body in Streamlit.
    """
    try:
        r = e.response
        if r is not None:
            try:
                err_json = r.json()
                # common fastapi detail format: {"detail": "..."}
                if isinstance(err_json, dict):
                    detail = err_json.get("detail") or err_json.get("error", {}).get("message")
                    if detail:
                        st.error(str(detail))
                    else:
                        st.error(str(e))
                    with st.expander("Error details"):
                        st.json(err_json)
                else:
                    st.error(str(e))
                    with st.expander("Error body"):
                        st.write(err_json)
            except Exception:
                st.error(str(e))
                with st.expander("Raw error body"):
                    st.code(r.text or "", language="text")
        else:
            st.error(str(e))
    except Exception:
        st.error(str(e))


def _looks_like_json(s: str) -> bool:
    s2 = (s or "").lstrip()
    return s2.startswith("{") or s2.startswith("[")


def _looks_like_yaml(s: str) -> bool:
    s2 = (s or "").strip()
    return any(s2.startswith(p) for p in ["version:", "meta:", "target:", "change:", "requirements:"])


# ----------------------------
# Tabs (NAMED) - prevents index mismatch bugs
# ----------------------------
tab_build, tab_build_v2, tab_intent, tab_sync, tab_dq, tab_stage8, tab_trouble, tab_validate = st.tabs(
    [
        "Build",
        "Build (v2)",
        "Build (Intent)",
        "Sync Project",
        "Add DQ",
        "Stage 8",        # <-- missing tab added
        "Troubleshoot",
        "Validate",
    ]
)


# ----------------------------
# Tab: Build (kept as your main Build UI)
# ----------------------------
with tab_build:
    st.header("Build")
    st.write("Generates Spark job + Airflow DAG + Spark config from UI inputs (Build V2 API).")

    c1, c2, c3 = st.columns(3)
    with c1:
        job_name = st.text_input("Job name", value="example_pipeline")
    with c2:
        owner = st.text_input("Owner", value="data-platform")
    with c3:
        schedule = st.text_input("Schedule (cron)", value="0 6 * * *")

    c4, c5, c6 = st.columns(3)
    with c4:
        language = st.selectbox("Language", ["pyspark", "scala"], index=0)
    with c5:
        env = st.selectbox("Environment", ["dev", "qa", "prod"], index=0)
    with c6:
        timezone = st.text_input("Timezone", value="UTC")

    st.subheader("Source / Target")
    s1, s2 = st.columns(2)
    with s1:
        source_table = st.text_input("Source table", value="raw_db.source_table")
    with s2:
        target_table = st.text_input("Target table", value="curated_db.target_table")

    s3, s4, s5 = st.columns([2, 2, 2])
    with s3:
        partition_column = st.text_input("Partition column", value="data_dt")
    with s4:
        write_mode = st.selectbox("Write mode", ["merge", "append", "overwrite"], index=0)
    with s5:
        spark_da = st.checkbox("Spark dynamic allocation", value=True)

    st.subheader("Enterprise presets (public)")
    p1, p2 = st.columns([2, 3])
    with p1:
        preset = st.selectbox("Preset", ["generic", "enterprise_a", "enterprise_b"], index=0)
    with p2:
        description = st.text_input("Job description", value="Example Spark pipeline generated by Copilot")

    preset_cfg = PRESET_DEFAULTS.get(preset, PRESET_DEFAULTS["generic"])
    tags = st.text_input("Tags (comma-separated)", value=",".join(preset_cfg.get("tags", [])))

    st.caption("Spark conf overrides (advanced) — JSON object of key/value strings")
    spark_overrides_default = preset_cfg.get("spark_conf_overrides", {})
    spark_conf_overrides = st.text_area(
        "spark_conf_overrides",
        value=json.dumps(spark_overrides_default, indent=2, sort_keys=True),
        height=140,
    )

    st.subheader("Optional")
    dq_enabled = st.checkbox("Enable DQ (placeholder)", value=False)
    troubleshoot_enabled = st.checkbox("Enable Troubleshoot (placeholder)", value=False)

    if st.button("Generate Project", type="primary"):
        start = time.time()
        try:
            overrides_obj: Dict[str, str] = {}
            txt = (spark_conf_overrides or "").strip()
            if txt:
                overrides_obj = json.loads(txt)

            payload = {
                "spec": {
                    "job_name": job_name.strip(),
                    "preset": preset,
                    "owner": owner.strip(),
                    "env": env,
                    "schedule": schedule.strip(),
                    "timezone": timezone.strip(),
                    "description": description.strip(),
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "source_table": source_table.strip(),
                    "target_table": target_table.strip(),
                    "partition_column": partition_column.strip(),
                    "write_mode": write_mode,
                    "language": language,
                    "spark_dynamic_allocation": bool(spark_da),
                    "spark_conf_overrides": overrides_obj,
                    "dq_enabled": bool(dq_enabled),
                    "troubleshoot_enabled": bool(troubleshoot_enabled),
                },
                "write_spec_yaml": True,
            }

            data = api_post_json("/build/v2", payload)
            st.success(data.get("message", "Build V2 completed"))
            st.caption(f"Build completed in {time.time() - start:.2f} seconds")
            st.json(data)

        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON in spark_conf_overrides: {e}")
        except requests.HTTPError as e:
            show_http_error(e)
        except Exception as e:
            st.error(f"Build failed: {e}")

# ----------------------------
# Tab: Build (v2) - optional separate tab; keep as helper/placeholder
# ----------------------------
with tab_build_v2:
    st.header("Build (v2)")
    st.info(
        "This tab is optional. Your current Build UI already calls `/build/v2`.\n\n"
        "If you want, we can later move the Build UI here and use `Build` for legacy `/build`."
    )
    st.caption(f"API_URL currently: {API_URL}")

# ----------------------------
# Tab: Build (Intent)
# ----------------------------
with tab_intent:
    st.header("Build (Intent)")
    st.write("Requirement → Parsed Spec → Reuse Build V2 pipeline (deterministic parser; no LLM).")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        intent_job_name = st.text_input(
            "Workspace job name (optional)",
            value="example_pipeline",
            help="Used as repo workspace context if your backend supports job-scoped repos.",
            key="intent_job_name",
        )
    with c2:
        parse_mode = st.selectbox("Parse mode", ["auto", "dsl", "yaml", "json"], index=0, key="intent_parse_mode")
    with c3:
        strict_mode = st.checkbox("Strict validation", value=True, key="intent_strict_mode")

    st.caption("Paste your requirement in DSL Markdown (recommended) OR YAML/JSON IntentSpec.")
    requirement_text = st.text_area(
        "Requirement / Spec",
        value=INTENT_DSL_TEMPLATE,
        height=320,
        key="intent_requirement_text",
    )

    o1, o2, o3, o4 = st.columns(4)
    with o1:
        allow_partial = st.checkbox("Allow partial", value=False, key="intent_allow_partial")
    with o2:
        dry_run = st.checkbox("Dry run (no build)", value=False, key="intent_dry_run")
    with o3:
        default_repo = st.text_input("Default repo", value="data-platform-copilot", key="intent_default_repo")
    with o4:
        default_branch = st.text_input("Default branch", value="main", key="intent_default_branch")

    ctx1, ctx2 = st.columns(2)
    with ctx1:
        ctx_repo = st.text_input("Context repo override (optional)", value="", key="intent_ctx_repo")
    with ctx2:
        ctx_paths = st.text_input(
            "Context paths (comma-separated)",
            value="jobs,dags,configs,ui,app",
            key="intent_ctx_paths",
        )

    if st.button("Parse & Build", type="primary", key="intent_parse_build"):
        start = time.time()
        try:
            req = (requirement_text or "").strip()
            if not req:
                st.warning("Requirement/spec is empty.")
                st.stop()

            hinted_mode = parse_mode
            if parse_mode == "auto":
                if _looks_like_json(req):
                    hinted_mode = "json"
                elif _looks_like_yaml(req):
                    hinted_mode = "yaml"
                else:
                    hinted_mode = "dsl"

            if hinted_mode == "json":
                try:
                    json.loads(req)
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
                    st.stop()

            payload = {
                "requirement": req,
                "mode": hinted_mode,
                "options": {
                    "strict": bool(strict_mode),
                    "allow_partial": bool(allow_partial),
                    "dry_run": bool(dry_run),
                    "default_repo": default_repo.strip() or None,
                    "default_branch": default_branch.strip() or None,
                },
                "context": {
                    "job_name": intent_job_name.strip() or None,
                    "repo": ctx_repo.strip() or None,
                    "paths": [p.strip() for p in (ctx_paths or "").split(",") if p.strip()],
                },
            }

            data = api_post_json("/build/intent", payload)
            st.success(data.get("message", "Intent parsed successfully"))
            st.caption(f"Completed in {time.time() - start:.2f} seconds")

            # Show common backend response keys (your backend may return a simpler shape)
            if "parsed_spec" in data:
                st.subheader("Parsed Spec")
                st.json(data["parsed_spec"])
            if "warnings" in data:
                st.subheader("Warnings")
                st.json(data["warnings"])
            if "confidence" in data:
                st.metric("Confidence", data["confidence"])
            if "spec_hash" in data:
                st.code(f"spec_hash: {data['spec_hash']}", language="text")

            if "build_result" in data:
                st.subheader("Build Result")
                st.json(data["build_result"])

            # Keep support for earlier response shape too
            if "intent_spec" in data:
                st.subheader("Parsed Intent Spec")
                st.json(data["intent_spec"])
            if "build_plan" in data:
                st.subheader("Compiled Build Plan")
                st.json(data["build_plan"])
            if "build" in data:
                st.subheader("Build")
                st.json(data["build"])

            diag = data.get("diagnostics")
            if diag:
                with st.expander("Diagnostics"):
                    st.json(diag)

        except requests.HTTPError as e:
            show_http_error(e)
        except Exception as e:
            st.error(f"Intent build failed: {e}")

# ----------------------------
# Tab: Sync Project
# ----------------------------
with tab_sync:
    st.header("Sync Project")
    st.write("Analyze user-modified code and detect drift (baseline → HEAD).")

    jobs = list_workspace_jobs()
    if not jobs:
        st.info("No workspace jobs found yet. Run **Build → Generate Project** first.")
        st.stop()

    col1, col2 = st.columns([3, 1])
    with col1:
        job_name_sel = st.selectbox("Select workspace job", jobs, index=0, key="sync_job_select")
    with col2:
        if st.button("Refresh", use_container_width=True, key="sync_refresh"):
            st.rerun()

    # Repo status
    try:
        status_resp = api_get("/repo/status", params={"job_name": job_name_sel})
        status = status_resp.get("status", {})
        baseline_commit = status_resp.get("baseline_commit")
        repo_dir = status_resp.get("repo_dir")

        branch = status.get("branch", "(unknown)")
        dirty = bool(status.get("dirty"))
        porcelain = status.get("porcelain", []) or []

        a, b, c = st.columns(3)
        a.metric("Job", job_name_sel)
        b.metric("Branch", branch)
        c.metric("Working Tree", "✅ Clean" if not dirty else "⚠️ Dirty")

        st.caption(f"Repo dir: {repo_dir}")
        st.code(f"Baseline commit: {baseline_commit or '(not set)'}", language="text")

        if porcelain:
            st.subheader("Changed files (working tree)")
            rows = []
            for line in porcelain:
                if len(line) >= 4:
                    rows.append({"status": line[:2].strip(), "path": line[3:]})
                else:
                    rows.append({"status": "", "path": line})
            st.table(rows)
        else:
            st.info("No uncommitted changes detected (git status clean).")

    except requests.HTTPError as e:
        show_http_error(e)
        st.stop()
    except Exception as e:
        st.error(f"Failed to fetch repo status: {e}")
        st.stop()

    # Diff preview
    st.subheader("Diff (baseline → HEAD)")
    try:
        diff_resp = api_get("/repo/diff", params={"job_name": job_name_sel})
        diff_text = diff_resp.get("diff", "") or ""
    except requests.HTTPError as e:
        show_http_error(e)
        st.stop()
    except Exception as e:
        st.error(f"Failed to fetch diff: {e}")
        st.stop()

    with st.expander("Show diff"):
        if diff_text.strip():
            st.code(diff_text, language="diff")
        else:
            st.write("No diff between baseline and HEAD.")

    # Upstream section
    st.divider()
    st.subheader("Upstream (Enterprise Freshness)")

    default_repo_url = os.environ.get("COPILOT_UPSTREAM_REPO_URL", "")
    default_branch = os.environ.get("COPILOT_UPSTREAM_BRANCH", "main")

    repo_url = st.text_input(
        "Upstream repo URL",
        value=default_repo_url,
        placeholder="https://... or git@... (read-only)",
        key="up_repo_url",
    )
    branch_up = st.text_input("Upstream branch", value=default_branch, key="up_branch")

    scope_paths = st.text_input(
        "Upstream scope (comma-separated paths)",
        value=os.environ.get("COPILOT_UPSTREAM_PATHS", "app,ui,copilot_spec.yaml"),
        key="up_scope_paths",
    )

    st.caption("Upstream config summary (auto-loaded)")
    upstream_summary = None
    upstream_err = None
    try:
        upstream_summary = api_get(
            "/repo/upstream/status",
            params={"job_name": job_name_sel, "paths": scope_paths},
        )
    except Exception as e:
        upstream_err = str(e)

    if upstream_summary:
        note = upstream_summary.get("note")
        if note:
            st.info(note)

        cfg = upstream_summary.get("upstream", {}) or {}
        ab = upstream_summary.get("ahead_behind", {}) or {}
        files = upstream_summary.get("files_changed_vs_upstream", []) or []

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Ahead", int(ab.get("ahead", 0)))
        s2.metric("Behind", int(ab.get("behind", 0)))
        s3.metric("File drift (scoped)", len(files))
        s4.metric("Upstream ref", upstream_summary.get("upstream_ref", "") or "-")

        st.write(
            f"**Remote:** `{cfg.get('remote', '-')}`  \n"
            f"**Repo:** `{cfg.get('repo_url', '-')}`  \n"
            f"**Branch:** `{cfg.get('branch', '-')}`  \n"
            f"**Connected at:** `{cfg.get('connected_at', '-')}`  \n"
            f"**Last fetch at:** `{cfg.get('last_fetch_at', '-')}`  \n"
            f"**Upstream head:** `{upstream_summary.get('upstream_head', '-')}`"
        )
    else:
        st.info("Upstream not connected (or not fetched yet). Use **Connect upstream** → **Fetch upstream**.")
        with st.expander("Debug (upstream status error)"):
            st.code(upstream_err or "No error details", language="text")

    c1, c2, c3 = st.columns(3)
    with c1:
        connect_clicked = st.button("Connect upstream", use_container_width=True, key="up_connect")
    with c2:
        fetch_clicked = st.button("Fetch upstream", use_container_width=True, key="up_fetch")
    with c3:
        status_clicked = st.button("Refresh upstream status", use_container_width=True, key="up_status")

    if connect_clicked:
        if not repo_url.strip():
            st.warning("Please provide an upstream repo URL.")
        else:
            try:
                r = requests.post(
                    f"{API_URL}/repo/upstream/connect",
                    params={"job_name": job_name_sel, "repo_url": repo_url.strip(), "branch": branch_up.strip() or "main"},
                    timeout=30,
                )
                _raise_for_status_with_body(r)
                st.success("Upstream connected.")
                st.json(r.json())
            except requests.HTTPError as e:
                show_http_error(e)
            except Exception as e:
                st.error(f"Upstream connect failed: {e}")

    if fetch_clicked:
        try:
            r = requests.post(f"{API_URL}/repo/upstream/fetch", params={"job_name": job_name_sel}, timeout=60)
            _raise_for_status_with_body(r)
            st.success("Upstream fetched.")
            st.json(r.json())
        except requests.HTTPError as e:
            show_http_error(e)
        except Exception as e:
            st.error(f"Upstream fetch failed: {e}")

    if status_clicked:
        try:
            up = api_get("/repo/upstream/status", params={"job_name": job_name_sel, "paths": scope_paths})
            note = up.get("note")
            if note:
                st.info(note)

            ab = up.get("ahead_behind", {}) or {}
            a2, b2, c2 = st.columns(3)
            a2.metric("Ahead (workspace vs upstream)", int(ab.get("ahead", 0)))
            b2.metric("Behind (workspace vs upstream)", int(ab.get("behind", 0)))
            c2.metric("Upstream ref", up.get("upstream_ref", ""))

            files = up.get("files_changed_vs_upstream", []) or []
            if files:
                st.write("### Files changed vs upstream (scoped)")
                st.table([{"path": f} for f in files])
            else:
                st.info("No file-level drift vs upstream (scoped).")

            with st.expander("Show upstream diff (upstream → workspace)"):
                d = api_get(
                    "/repo/upstream/diff",
                    params={"job_name": job_name_sel, "direction": "upstream_to_workspace", "max_chars": 20000},
                ).get("diff", "")
                st.code(d if d else "No diff.", language="diff")
        except requests.HTTPError as e:
            show_http_error(e)
        except Exception as e:
            st.error(f"Upstream status failed: {e}")

# ----------------------------
# Tab: Add DQ (placeholder)
# ----------------------------
with tab_dq:
    st.header("Add DQ")
    st.info("Generate Data Quality checks when required (placeholder).")

# ----------------------------
# Tab: Stage 8
# ----------------------------
with tab_stage8:
    st.header("Stage 8")
    st.caption("Semantic diff, conflict UX, remotes, advisor impact graph.")

    st.subheader("Semantic Diff")
    sd_job = st.text_input("job_name", value="", key="s8_sd_job")
    col1, col2 = st.columns(2)
    sd_ref_a = col1.text_input("ref_a", value="HEAD", key="s8_sd_a")
    sd_ref_b = col2.text_input("ref_b", value="upstream/main", key="s8_sd_b")
    sd_paths = st.text_input("paths (comma-separated, optional)", value="", key="s8_sd_paths")
    if st.button("Run semantic diff"):
        if not sd_job.strip():
            st.error("job_name is required")
        else:
            try:
                params = {"job_name": sd_job, "ref_a": sd_ref_a, "ref_b": sd_ref_b}
                if sd_paths.strip():
                    params["paths"] = sd_paths
                data = api_get("/repo/semantic-diff", params=params)
                st.json(data)
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("Conflicts")
    c_job = st.text_input("job_name (conflicts)", value="", key="s8_c_job")
    colc1, colc2 = st.columns(2)
    if colc1.button("Detect conflicts"):
        try:
            data = api_get("/repo/conflicts", params={"job_name": c_job})
            st.json(data)
        except Exception as e:
            st.error(str(e))
    if colc2.button("Conflict help"):
        try:
            data = api_get("/repo/conflicts/help", params={"job_name": c_job})
            st.json(data)
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.subheader("Remotes (Sources/Templates)")
    r_job = st.text_input("job_name (remotes)", value="", key="s8_r_job")
    if st.button("List remotes"):
        try:
            st.json(api_get("/repo/remotes", params={"job_name": r_job}))
        except Exception as e:
            st.error(str(e))

    with st.expander("Add remote"):
        r_name = st.text_input("name", value="", key="s8_r_name")
        r_url = st.text_input("url", value="", key="s8_r_url")
        if st.button("Add"):
            try:
                resp = requests.post(f"{API_URL}/repo/remotes/add", params={"job_name": r_job}, json={"name": r_name, "url": r_url}, timeout=30)
                resp.raise_for_status()
                st.json(resp.json())
            except Exception as e:
                st.error(str(e))

    with st.expander("Fetch + Status"):
        f_name = st.text_input("remote name", value="upstream", key="s8_f_name")
        f_branch = st.text_input("branch", value="main", key="s8_f_branch")
        colf1, colf2 = st.columns(2)
        if colf1.button("Fetch"):
            try:
                resp = requests.post(f"{API_URL}/repo/remotes/fetch", params={"job_name": r_job}, json={"name": f_name}, timeout=30)
                resp.raise_for_status()
                st.json(resp.json())
            except Exception as e:
                st.error(str(e))
        if colf2.button("Status"):
            try:
                st.json(api_get("/repo/remotes/status", params={"job_name": r_job, "name": f_name, "branch": f_branch}))
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("Advisor Impact Graph")
    ig_job = st.text_input("job_name (impact graph)", value="", key="s8_ig_job")
    ig_plan = st.text_input("plan_id", value="", key="s8_ig_plan")
    if st.button("Load impact graph"):
        try:
            st.json(api_get("/advisors/impact-graph", params={"job_name": ig_job, "plan_id": ig_plan}))
        except Exception as e:
            st.error(str(e))

with tab_stage10:
    st.subheader("Stage 10 — Repro Compare + Release Verify + Manifest Drift Gate")

    st.markdown("### Workspace Repro Compare")
    col1, col2 = st.columns(2)
    with col1:
        job_a = st.text_input("job_a", value="example_pipeline")
    with col2:
        job_b = st.text_input("job_b", value="example_pipeline")

    if st.button("Compare manifests"):
        try:
            resp = api_get("/workspace/repro/compare", params={"job_a": job_a, "job_b": job_b})
            st.json(resp)
        except Exception as e:
            st.error(str(e))

    st.markdown("### Release Tarball Verify (local path)")
    tar_path = st.text_input("tarball_path", value="data-platform-copilot.tar.gz")
    sha_path = st.text_input("expected_sha256 (paste)", value="")

    require_manifest = st.checkbox("Require packaging_manifest.json inside tarball", value=True)

    if st.button("Verify tarball"):
        try:
            payload = {
                "tarball_path": tar_path,
                "expected_sha256": sha_path.strip(),
                "require_packaging_manifest": require_manifest,
            }
            resp = api_post("/release/verify/tarball", payload)
            st.json(resp)
        except Exception as e:
            st.error(str(e))

    st.markdown("### Packaging Manifest")
    st.code("make manifest-gen  # generate packaging_manifest.json\nmake manifest-check  # drift gate", language="bash")


# ----------------------------
# Tab: Troubleshoot (placeholder)
# ----------------------------
with tab_trouble:
    st.header("Troubleshoot")
    st.info("Analyze failures from logs and suggest fixes (placeholder).")

# ----------------------------
# Tab: Validate (placeholder)
# ----------------------------
with tab_validate:
    st.header("Validate")
    st.info("Run linting, parsing, and DAG import checks (placeholder).")

