import pytest

from app.core.sync.guardrails import validate_baseline


def test_head_drift_detection(tmp_repo):
    with pytest.raises(Exception):
        validate_baseline(tmp_repo, "abc123deadbeef")