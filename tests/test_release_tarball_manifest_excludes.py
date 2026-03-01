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


def test_tarball_excludes_node_artifacts():
    assert _is_excluded("frontend/node_modules/react/index.js")
    assert _is_excluded("node_modules/lodash/lodash.js")
    assert _is_excluded("frontend/.vite/deps/react.js")


def test_tarball_excludes_agent_working_docs():
    assert _is_excluded("antigravity_prompt_v5.md")
    assert _is_excluded("antigravity_prompt_v4.md")
    assert _is_excluded("antigravity_prompt_v99.md")


def test_tarball_still_includes_source_md():
    assert not _is_excluded("CLAUDE.md")
    assert not _is_excluded("KNOWN_LIMITATIONS.md")
    assert not _is_excluded("README.md")
    assert not _is_excluded("docs/RUNBOOK.md")


def test_tarball_excludes_secret_txt_files():
    assert _is_excluded("deploy/secrets/admin_token.txt")
    assert _is_excluded("deploy/secrets/viewer_token.txt")
    assert _is_excluded("deploy/secrets/signing_key.txt")
    assert _is_excluded("deploy/secrets/llm_api_key.txt")


def test_tarball_includes_secrets_readme_and_setup():
    # README and setup.sh must be included — only .txt credential files are excluded
    assert not _is_excluded("deploy/secrets/README.md")
    assert not _is_excluded("deploy/secrets/setup.sh")

