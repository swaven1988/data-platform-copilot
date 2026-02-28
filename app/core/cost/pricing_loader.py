"""
Phase G — Pricing calibration loader.

Reads an optional YAML/JSON pricing override file and merges it with the
built-in static tables.  This allows production repricing without code changes.

Override file format (YAML or JSON):
    aws/us-east-1: 0.035
    gcp/us-central1: 0.041
    k8s/default: 0.038

Environment variable:
    COPILOT_PRICING_FILE — path to the override file (optional).
    Default search path: <project_root>/pricing_overrides.yaml
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

_log = logging.getLogger("copilot.pricing")

PriceTable = Dict[Tuple[str, str], float]


def _parse_override_dict(raw: dict) -> PriceTable:
    """Convert {"aws/us-east-1": 0.035} → {("aws", "us-east-1"): 0.035}."""
    out: PriceTable = {}
    for key, value in raw.items():
        try:
            parts = str(key).split("/", 1)
            if len(parts) != 2:
                _log.warning("Skipping invalid pricing key %r (expected 'provider/region')", key)
                continue
            provider, region = parts[0].strip().lower(), parts[1].strip().lower()
            out[(provider, region)] = float(value)
        except (ValueError, TypeError) as exc:
            _log.warning("Skipping invalid pricing entry %r: %s", key, exc)
    return out


def load_pricing_overrides(path: Optional[Path] = None) -> PriceTable:
    """
    Load pricing overrides from a YAML or JSON file.

    Returns an empty dict if the file is absent, not readable, or malformed
    — the caller should fall back to built-in defaults in that case.
    """
    resolved = _resolve_path(path)
    if resolved is None or not resolved.exists():
        return {}

    raw_text = ""
    try:
        raw_text = resolved.read_text(encoding="utf-8")
        # Try JSON first (superset of YAML numbers/strings for simple flat dicts)
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fall back to YAML
            try:
                import yaml  # type: ignore[import]
                data = yaml.safe_load(raw_text)
            except Exception as exc:
                _log.warning("Failed to parse pricing file %s as JSON or YAML: %s", resolved, exc)
                return {}

        if not isinstance(data, dict):
            _log.warning("Pricing override file %s must be a flat mapping, got %s", resolved, type(data).__name__)
            return {}

        overrides = _parse_override_dict(data)
        if overrides:
            _log.info("Loaded %d pricing overrides from %s", len(overrides), resolved)
        return overrides

    except OSError as exc:
        _log.warning("Cannot read pricing override file %s: %s", resolved, exc)
        return {}


def _resolve_path(path: Optional[Path]) -> Optional[Path]:
    """Determine the override file path from argument or env var or default."""
    if path is not None:
        return Path(path)
    env_path = os.getenv("COPILOT_PRICING_FILE", "").strip()
    if env_path:
        return Path(env_path)
    # Default: project root / pricing_overrides.yaml
    project_root = Path(__file__).resolve().parents[3]
    default = project_root / "pricing_overrides.yaml"
    return default
