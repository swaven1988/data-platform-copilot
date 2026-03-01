"""Regression tests for deterministic tarball excludes vs packaging manifest."""

from __future__ import annotations

from tools.build_release_tarball import _is_excluded


def test_tarball_excludes_align_with_manifest_style_patterns():
    # Existing exclusions from packaging workflow
    assert _is_excluded("app/__pycache__/mod.cpython-311.pyc")
    assert _is_excluded(".venv/Lib/site-packages/pkg.py")
    assert _is_excluded("workspace/job_a/.copilot/execution/run.json")
    assert _is_excluded("logs/service.log")


def test_tarball_includes_regular_project_files():
    assert not _is_excluded("app/api/main.py")
    assert not _is_excluded("tools/gen_packaging_manifest.py")
    assert not _is_excluded("tests/test_openapi_snapshot.py")

