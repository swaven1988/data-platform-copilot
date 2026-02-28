"""
Ensures VERSION, release_metadata.json, and Helm chart appVersion are consistent.
Prevents version split regressions from recurring.
This test only validates consistency and does not infer semantic release correctness.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _read_metadata_version() -> str:
    return json.loads((ROOT / "release_metadata.json").read_text(encoding="utf-8"))["version"]


def _read_helm_app_version() -> str:
    chart = (ROOT / "deploy" / "helm" / "data-platform-copilot" / "Chart.yaml").read_text(encoding="utf-8")
    for line in chart.splitlines():
        if line.strip().startswith("appVersion:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise ValueError("appVersion not found in Chart.yaml")


def test_version_file_matches_release_metadata():
    v = _read_version()
    m = _read_metadata_version()
    assert v == m, f"VERSION={v} but release_metadata.json version={m}"


def test_version_file_matches_helm_chart():
    v = _read_version()
    h = _read_helm_app_version()
    assert v == h, f"VERSION={v} but Chart.yaml appVersion={h}"
