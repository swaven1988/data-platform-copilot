"""
Phase C — PySpark preset catalog tests.

Verifies that generate_pyspark_job() produces syntactically valid Python
for every catalogued preset and that NotImplementedError is gone.
"""
from __future__ import annotations

import ast
import pytest

from app.core.generators.pyspark_gen import generate_pyspark_job, _PRESET_CATALOG
from app.core.spec_schema import CopilotSpec


def _make_spec(preset: str) -> CopilotSpec:
    return CopilotSpec(
        job_name="test_job",
        source_table="raw.events",
        target_table="curated.events",
        partition_column="event_date",
        write_mode="overwrite",
        preset=preset,
        language="pyspark",
    )


def _make_spec_raw(preset: str, write_mode: str = "overwrite") -> CopilotSpec:
    """Bypass pydantic validation for testing non-schema values."""
    return CopilotSpec.model_construct(
        job_name="test_job",
        source_table="raw.events",
        target_table="curated.events",
        partition_column="event_date",
        write_mode=write_mode,
        preset=preset,
        language="pyspark",
    )


# All presets now defined in the schema AND in the catalog
KNOWN_PRESETS = list(_PRESET_CATALOG.keys())


@pytest.mark.parametrize("preset", KNOWN_PRESETS)
def test_known_preset_produces_valid_python(preset: str):
    files = generate_pyspark_job(_make_spec(preset))
    assert len(files) == 1, "Expected exactly one output file"
    code = next(iter(files.values()))

    # Must be parseable Python
    try:
        ast.parse(code)
    except SyntaxError as exc:
        pytest.fail(f"Preset '{preset}' generated invalid Python: {exc}")

    # Must NOT raise NotImplementedError
    assert "NotImplementedError" not in code, (
        f"Preset '{preset}' still contains NotImplementedError"
    )


def test_unknown_preset_falls_back_gracefully():
    """Unknown presets (bypassing schema validation) should NOT raise — fallback passthrough."""
    files = generate_pyspark_job(_make_spec_raw("totally_unknown_preset"))
    code = next(iter(files.values()))
    assert "NotImplementedError" not in code
    assert "PRESET_NOT_IMPLEMENTED" in code   # has the fallback comment
    ast.parse(code)                            # still valid Python


def test_output_file_path_matches_job_name():
    files = generate_pyspark_job(_make_spec("copy"))
    assert "jobs/pyspark/src/test_job.py" in files


@pytest.mark.parametrize("write_mode", ["overwrite", "append", "merge"])
def test_write_modes_produce_valid_code(write_mode: str):
    spec = _make_spec_raw("copy", write_mode=write_mode)
    spec = CopilotSpec(
        job_name="wm_test",
        source_table="src.t",
        target_table="dst.t",
        partition_column="dt",
        write_mode=write_mode,
        preset="copy",
        language="pyspark",
    )
    files = generate_pyspark_job(spec)
    ast.parse(next(iter(files.values())))


def test_invalid_write_mode_raises():
    """An invalid write_mode (bypassing schema) should raise ValueError in the generator."""
    spec = CopilotSpec.model_construct(
        job_name="bad_wm",
        source_table="src.t",
        target_table="dst.t",
        partition_column="dt",
        write_mode="invalid_mode",
        preset="copy",
        language="pyspark",
    )
    with pytest.raises(ValueError, match="Unsupported write_mode"):
        generate_pyspark_job(spec)
