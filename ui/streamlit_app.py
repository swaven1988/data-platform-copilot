import os
import time
import requests
from pathlib import Path
import streamlit as st
from typing import Optional, Dict, Any

try:
    API_URL = st.secrets["API_URL"]
except Exception:
    API_URL = "http://localhost:8001"

st.set_page_config(page_title="Data Platform Copilot", layout="wide")
st.title("🧠 Data Platform Copilot")

API_URL = API_URL.rstrip("/")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


def list_workspace_jobs() -> list[str]:
    if not WORKSPACE_ROOT.exists():
        return []
    return sorted([p.name for p in WORKSPACE_ROOT.iterdir() if p.is_dir()])


def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    resp = requests.get(f"{API_URL}{path}", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


tabs = st.tabs([
    "Build",
    "Sync Project",
    "Add DQ",
    "Troubleshoot",
    "Validate",
])

# ----------------------------
# Tab 0: Build
# ----------------------------
with tabs[0]:
    st.header("Build")
    st.write("Generates PySpark job + Airflow DAG + Spark config based on `copilot_spec.yaml`.")

    if st.button("Generate Project", type="primary", key="build_generate"):
        start = time.time()
        try:
            resp = requests.post(f"{API_URL}/build/", timeout=30)
            resp.raise_for_status()
            data = resp.json()

            st.success(data.get("message", "Build completed"))
            st.caption(f"Build completed in {time.time() - start:.2f} seconds")

            st.json(data)

            workspace_dir = data.get("workspace_dir")
            baseline_commit = data.get("baseline_commit")
            if workspace_dir or baseline_commit:
                st.subheader("Workspace + Baseline")
                if workspace_dir:
                    st.write(f"**Workspace:** `{workspace_dir}`")
                if baseline_commit:
                    st.write(f"**Baseline commit:** `{baseline_commit}`")

            st.subheader("Generated files")
            for f in data.get("files", []):
                st.write(f"- `{f}`")

            st.subheader("Zip output")
            zip_path = data.get("zip_path")
            st.code(zip_path)

            if zip_path and Path(zip_path).exists():
                with open(zip_path, "rb") as fp:
                    st.download_button(
                        label="Download ZIP",
                        data=fp,
                        file_name=Path(zip_path).name,
                        mime="application/zip",
                        key="build_zip_download",
                    )
            else:
                st.warning("Zip path not found on this machine. Check API output path.")

        except Exception as e:
            st.error(f"Build failed: {e}")

# ----------------------------
# Tab 1: Sync Project
# ----------------------------
with tabs[1]:
    st.header("Sync Project")
    st.write("Analyze user-modified code and detect drift (baseline → HEAD).")

    jobs = list_workspace_jobs()
    if not jobs:
        st.info("No workspace jobs found yet. Run **Build → Generate Project** first.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            job_name = st.selectbox("Select workspace job", jobs, index=0, key="sync_job_select")
        with col2:
            if st.button("Refresh", use_container_width=True, key="sync_refresh"):
                st.rerun()

        # Repo status
        try:
            status_resp = api_get("/repo/status", params={"job_name": job_name})
            status = status_resp.get("status", {})
            baseline_commit = status_resp.get("baseline_commit")
            repo_dir = status_resp.get("repo_dir")

            branch = status.get("branch", "(unknown)")
            dirty = bool(status.get("dirty"))
            porcelain = status.get("porcelain", []) or []

            a, b, c = st.columns(3)
            a.metric("Job", job_name)
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

        except Exception as e:
            st.error(f"Failed to fetch repo status: {e}")
            st.stop()

        # Diff preview
        st.subheader("Diff (baseline → HEAD)")
        try:
            diff_resp = api_get("/repo/diff", params={"job_name": job_name})
            diff_text = diff_resp.get("diff", "") or ""
        except Exception as e:
            st.error(f"Failed to fetch diff: {e}")
            st.stop()

        with st.expander("Show diff"):
            if diff_text.strip():
                st.code(diff_text, language="diff")
            else:
                st.write("No diff between baseline and HEAD.")

        # ----------------------------
        # Upstream (Enterprise Freshness)
        # ----------------------------
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

        # --- Upstream config summary (auto-load) ---
        st.caption("Upstream config summary (auto-loaded)")

        upstream_summary = None
        upstream_err = None
        try:
            upstream_summary = api_get(
                "/repo/upstream/status",
                params={"job_name": job_name, "paths": scope_paths},
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
                        params={
                            "job_name": job_name,
                            "repo_url": repo_url.strip(),
                            "branch": branch_up.strip() or "main",
                        },
                        timeout=30,
                    )
                    r.raise_for_status()
                    st.success("Upstream connected.")
                    st.json(r.json())
                except Exception as e:
                    st.error(f"Upstream connect failed: {e}")

        if fetch_clicked:
            try:
                r = requests.post(
                    f"{API_URL}/repo/upstream/fetch",
                    params={"job_name": job_name},
                    timeout=60,
                )
                r.raise_for_status()
                st.success("Upstream fetched.")
                st.json(r.json())
            except Exception as e:
                st.error(f"Upstream fetch failed: {e}")

        if status_clicked:
            try:
                up = api_get(
                    "/repo/upstream/status",
                    params={"job_name": job_name, "paths": scope_paths},
                )

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
                        params={"job_name": job_name, "direction": "upstream_to_workspace", "max_chars": 20000},
                    ).get("diff", "")
                    st.code(d if d else "No diff.", language="diff")

            except Exception as e:
                st.error(f"Upstream status failed: {e}")

# ----------------------------
# Tab 2: Add DQ
# ----------------------------
with tabs[2]:
    st.header("Add DQ")
    st.info("Generate Data Quality checks when required.")

# ----------------------------
# Tab 3: Troubleshoot
# ----------------------------
with tabs[3]:
    st.header("Troubleshoot")
    st.info("Analyze failures from logs and suggest fixes.")

# ----------------------------
# Tab 4: Validate
# ----------------------------
with tabs[4]:
    st.header("Validate")
    st.info("Run linting, parsing, and DAG import checks.")
