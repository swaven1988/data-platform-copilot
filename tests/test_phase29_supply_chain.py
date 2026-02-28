"""
Phase 29 — Supply Chain verification unit tests.

Tests verify_artifact_integrity() directly without HTTP overhead.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.core.supply_chain.verification import verify_artifact_integrity, sha256_file


def _write_artifact(tmp_path: Path, content: bytes = b"hello supply chain") -> tuple[Path, Path]:
    artifact = tmp_path / "artifact.tar.gz"
    sha_file  = tmp_path / "artifact.tar.gz.sha256"
    artifact.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    sha_file.write_text(digest)
    return artifact, sha_file


def test_valid_artifact_returns_true(tmp_path):
    artifact, sha_file = _write_artifact(tmp_path)
    result = verify_artifact_integrity(artifact, sha_file)
    assert result["valid"] is True
    assert result["expected_sha"] == result["actual_sha"]


def test_missing_artifact_returns_false(tmp_path):
    artifact = tmp_path / "missing.tar.gz"
    sha_file  = tmp_path / "missing.tar.gz.sha256"
    sha_file.write_text("aabbcc")
    result = verify_artifact_integrity(artifact, sha_file)
    assert result["valid"] is False
    assert result["reason"] == "artifact_missing"


def test_missing_sha_file_returns_false(tmp_path):
    artifact = tmp_path / "artifact.tar.gz"
    artifact.write_bytes(b"data")
    sha_file = tmp_path / "artifact.tar.gz.sha256"
    result = verify_artifact_integrity(artifact, sha_file)
    assert result["valid"] is False
    assert result["reason"] == "sha_file_missing"


def test_tampered_artifact_returns_false(tmp_path):
    artifact, sha_file = _write_artifact(tmp_path, b"original content")
    # Overwrite artifact with different content
    artifact.write_bytes(b"tampered content")
    result = verify_artifact_integrity(artifact, sha_file)
    assert result["valid"] is False
    assert result["expected_sha"] != result["actual_sha"]


def test_sha256_file_helper(tmp_path):
    f = tmp_path / "test.bin"
    data = b"checksum test data"
    f.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert sha256_file(f) == expected
