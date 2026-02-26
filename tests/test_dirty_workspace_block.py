import pytest

from app.core.sync.guardrails import validate_clean_workspace


def test_dirty_workspace_blocks_apply(tmp_path):
    (tmp_path / "x.txt").write_text("dirty", encoding="utf-8")

    with pytest.raises(Exception):
        validate_clean_workspace(tmp_path)