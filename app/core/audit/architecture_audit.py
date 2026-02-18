from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: str  # info|warn|block
    message: str
    target: str


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def run_architecture_audit(project_root: Path) -> Dict:
    findings: List[AuditFinding] = []

    # 1) Ensure OpenAPI snapshot exists
    snap = project_root / "tests" / "snapshots" / "openapi_snapshot.json"
    if not snap.exists():
        findings.append(
            AuditFinding(
                code="audit.openapi_snapshot_missing",
                severity="block",
                message="OpenAPI snapshot missing. Contract governance not enforced.",
                target=str(snap),
            )
        )

    # 2) Ensure release workflow exists
    rel = project_root / ".github" / "workflows" / "release.yml"
    if not rel.exists():
        findings.append(
            AuditFinding(
                code="audit.release_workflow_missing",
                severity="warn",
                message="Release workflow missing. Tag-based releases not automated.",
                target=str(rel),
            )
        )

    # 3) Detect hardcoded localhost in UI (warn only)
    ui = project_root / "ui" / "streamlit_app.py"
    if ui.exists():
        txt = _read_text(ui)
        if "localhost" in txt or "127.0.0.1" in txt:
            findings.append(
                AuditFinding(
                    code="audit.ui_hardcoded_host",
                    severity="info",
                    message="UI references localhost/127.0.0.1. Acceptable for local dev; ensure secrets/config for deployment.",
                    target=str(ui),
                )
            )

    # 4) Ensure CI workflow enforces snapshot test (heuristic)
    ci = project_root / ".github" / "workflows" / "ci.yml"
    if ci.exists():
        txt = _read_text(ci)
        if "test_openapi_snapshot.py" not in txt and "verify-snapshot" not in txt:
            findings.append(
                AuditFinding(
                    code="audit.ci_missing_snapshot_guard",
                    severity="warn",
                    message="CI does not appear to enforce OpenAPI snapshot consistency.",
                    target=str(ci),
                )
            )

    # 5) Basic repo hygiene checks (warn)
    if not (project_root / "README.md").exists():
        findings.append(
            AuditFinding(
                code="audit.readme_missing",
                severity="warn",
                message="README.md missing.",
                target=str(project_root / "README.md"),
            )
        )

    # summarize
    sev_rank = {"info": 0, "warn": 1, "block": 2}
    max_sev = "info"
    for f in findings:
        if sev_rank.get(f.severity, 0) > sev_rank.get(max_sev, 0):
            max_sev = f.severity

    return {
        "kind": "architecture_audit",
        "status": "PASS" if max_sev != "block" else "FAIL",
        "max_severity": max_sev,
        "findings": [
            {"code": f.code, "severity": f.severity, "message": f.message, "target": f.target}
            for f in findings
        ],
    }
