from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Result model (stable contract)
# ----------------------------
@dataclass
class ParseWarning:
    code: str
    message: str


@dataclass
class ParseResult:
    spec: Dict[str, Any]
    warnings: List[ParseWarning] = field(default_factory=list)
    confidence: float = 1.0
    explain: Dict[str, Any] = field(default_factory=dict)


# ----------------------------
# Helpers
# ----------------------------
_WS_RE = re.compile(r"\s+")


def _norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").strip())


def _first_match(patterns: List[re.Pattern], text: str) -> Optional[str]:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return (m.group(1) or "").strip()
    return None


def _safe_job_name(s: str) -> str:
    # Keep the same constraint as CopilotSpec: ^[a-zA-Z0-9_\-]+$
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_\-]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "example_pipeline"


def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [t.strip() for t in v.split(",") if t.strip()]
    return [str(v).strip()] if str(v).strip() else []


def _maybe_table(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = v.strip()
    # minimal sanity: db.table (alnum + _ only)
    if re.match(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$", v):
        return v
    return None


def _maybe_cron(expr: Optional[str]) -> Optional[str]:
    if not expr:
        return None
    expr = _norm_ws(expr)
    parts = expr.split(" ")
    # Build spec expects 5-field cron right now
    if len(parts) == 5 and all(p for p in parts):
        return expr
    return None


def _pick_enum(v: Optional[str], allowed: Tuple[str, ...]) -> Optional[str]:
    if not v:
        return None
    v2 = v.strip().lower()
    for a in allowed:
        if v2 == a:
            return a
    return None


# ----------------------------
# Deterministic parser (V1)
# ----------------------------
_PAT_JOB_NAME = [
    re.compile(r"\bjob\s*name\s*[:=]\s*([A-Za-z0-9_\-]+)\b", re.IGNORECASE),
    re.compile(r"\bpipeline\s*[:=]\s*([A-Za-z0-9_\-]+)\b", re.IGNORECASE),
]

_PAT_ENV = [
    re.compile(r"\benv(?:ironment)?\s*[:=]\s*(dev|qa|prod)\b", re.IGNORECASE),
]

_PAT_TIMEZONE = [
    re.compile(r"\btimezone\s*[:=]\s*([A-Za-z_\/]+)\b", re.IGNORECASE),
]

# "schedule: 0 6 * * *" / "cron 0 6 * * *"
_PAT_CRON = [
    re.compile(r"\bschedule\s*[:=]\s*([0-9\*\/,\-\s]+)\b", re.IGNORECASE),
    re.compile(r"\bcron\s*[:=]\s*([0-9\*\/,\-\s]+)\b", re.IGNORECASE),
]

_PAT_OWNER = [
    re.compile(r"\bowner\s*[:=]\s*([A-Za-z0-9_\-\.@]+)\b", re.IGNORECASE),
]

_PAT_LANGUAGE = [
    re.compile(r"\blanguage\s*[:=]\s*(pyspark|scala)\b", re.IGNORECASE),
    re.compile(r"\b(pyspark|scala)\b", re.IGNORECASE),  # fallback keyword
]

_PAT_SOURCE_TABLE = [
    re.compile(r"\bsource\s*table\s*[:=]\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\b", re.IGNORECASE),
    re.compile(r"\bread\s+from\s+([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\b", re.IGNORECASE),
]

_PAT_TARGET_TABLE = [
    re.compile(r"\btarget\s*table\s*[:=]\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\b", re.IGNORECASE),
    re.compile(r"\bwrite\s+to\s+([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\b", re.IGNORECASE),
]

_PAT_PARTITION_COL = [
    re.compile(r"\bpartition_column\s*[:=]\s*([A-Za-z0-9_]+)\b", re.IGNORECASE),
    re.compile(r"\bpartition(?:ed)?\s*(?:by)?\s*[:=]?\s*([A-Za-z0-9_]+)\b", re.IGNORECASE),
]

_PAT_WRITE_MODE = [
    re.compile(r"\bwrite\s*mode\s*[:=]\s*(merge|append|overwrite)\b", re.IGNORECASE),
    re.compile(r"\b(merge|append|overwrite)\b", re.IGNORECASE),  # fallback keyword
]


def parse_requirement_to_spec(
    requirement: str,
    job_name_hint: Optional[str],
    defaults: Dict[str, Any],
) -> ParseResult:
    """
    Deterministic conversion:
      requirement (free-text) -> CopilotSpec-compatible dict

    Design goals:
      - No LLM dependency
      - Stable contract (always emits keys required by CopilotSpec)
      - Emits structured warnings on fallback / sanitation
      - Extensible: add more patterns/rules later
    """
    text = _norm_ws(requirement or "")
    d = defaults or {}
    warnings: List[ParseWarning] = []

    # For "explain mode" support (returned always; API can choose to hide/show)
    explain: Dict[str, Any] = {
        "input": {"requirement": text, "job_name_hint": job_name_hint, "defaults_provided": sorted(list(d.keys()))},
        "matches": {},
        "defaults_used": [],
        "normalizations": [],
    }

    # --- preset (required by CopilotSpec) ---
    preset = d.get("preset") or "generic"
    if preset not in ("generic", "enterprise_a", "enterprise_b"):
        warnings.append(ParseWarning("preset.invalid", f"preset '{preset}' not recognized; defaulted to 'generic'"))
        explain["defaults_used"].append("preset=generic")
        preset = "generic"

    # --- job_name ---
    raw_job = _first_match(_PAT_JOB_NAME, text) or (job_name_hint or "") or str(d.get("job_name") or "")
    explain["matches"]["job_name_raw"] = raw_job or None
    job_name = _safe_job_name(raw_job)
    if not raw_job:
        warnings.append(ParseWarning("job_name.missing", "job_name missing; defaulted to example_pipeline"))
        explain["defaults_used"].append("job_name=example_pipeline")
    elif job_name != raw_job.strip():
        warnings.append(ParseWarning("job_name.sanitized", f"job_name sanitized to '{job_name}' from '{raw_job.strip()}'"))
        explain["normalizations"].append({"field": "job_name", "from": raw_job.strip(), "to": job_name})

    # --- env ---
    env_raw = _first_match(_PAT_ENV, text)
    explain["matches"]["env_raw"] = env_raw or None
    env = _pick_enum(env_raw, ("dev", "qa", "prod")) or str(d.get("env") or "dev").lower()
    if env not in ("dev", "qa", "prod"):
        warnings.append(ParseWarning("env.invalid", f"env '{env}' not recognized; defaulted to 'dev'"))
        explain["defaults_used"].append("env=dev")
        env = "dev"
    if not env_raw and "env" not in d:
        warnings.append(ParseWarning("env.missing", f"env missing; defaulted to {env}"))
        explain["defaults_used"].append(f"env={env}")

    # --- timezone ---
    tz_raw = _first_match(_PAT_TIMEZONE, text)
    explain["matches"]["timezone_raw"] = tz_raw or None
    timezone = tz_raw or str(d.get("timezone") or "UTC")
    timezone = timezone.strip() or "UTC"
    if not tz_raw and "timezone" not in d:
        explain["defaults_used"].append(f"timezone={timezone}")

    # --- schedule ---
    cron_raw = _first_match(_PAT_CRON, text)
    explain["matches"]["schedule_raw"] = cron_raw or None
    schedule = _maybe_cron(cron_raw) or _maybe_cron(str(d.get("schedule") or "")) or "0 6 * * *"
    if cron_raw and not _maybe_cron(cron_raw):
        warnings.append(ParseWarning("schedule.invalid", f"schedule '{cron_raw}' not valid 5-field cron; defaulted to {schedule!r}"))
        explain["normalizations"].append({"field": "schedule", "from": cron_raw, "to": schedule})
    if not cron_raw and "schedule" not in d:
        warnings.append(ParseWarning("schedule.missing", f"schedule missing; defaulted to {schedule!r}"))
        explain["defaults_used"].append(f"schedule={schedule!r}")

    # --- owner ---
    owner_raw = _first_match(_PAT_OWNER, text)
    explain["matches"]["owner_raw"] = owner_raw or None
    owner = owner_raw or str(d.get("owner") or "data-platform")
    owner = owner.strip() or "data-platform"
    if not owner_raw and "owner" not in d:
        explain["defaults_used"].append(f"owner={owner}")

    # --- description ---
    description = str(d.get("description") or "Generated from requirement").strip() or "Generated from requirement"
    if "description" not in d:
        explain["defaults_used"].append("description=Generated from requirement")

    # --- tags ---
    tags = _as_list(d.get("tags") or ["copilot", env])
    if "tags" not in d:
        explain["defaults_used"].append(f"tags={tags!r}")

    # --- language ---
    lang_raw = _first_match(_PAT_LANGUAGE, text)
    explain["matches"]["language_raw"] = lang_raw or None
    language = _pick_enum(lang_raw, ("pyspark", "scala")) or str(d.get("language") or "pyspark").lower()
    if language not in ("pyspark", "scala"):
        warnings.append(ParseWarning("language.invalid", f"language '{language}' not recognized; defaulted to 'pyspark'"))
        explain["defaults_used"].append("language=pyspark")
        language = "pyspark"
    if not lang_raw and "language" not in d:
        explain["defaults_used"].append(f"language={language}")

    # --- source / target ---
    src_raw = _first_match(_PAT_SOURCE_TABLE, text)
    tgt_raw = _first_match(_PAT_TARGET_TABLE, text)
    explain["matches"]["source_table_raw"] = src_raw or None
    explain["matches"]["target_table_raw"] = tgt_raw or None

    source_table = _maybe_table(src_raw) or _maybe_table(str(d.get("source_table") or "")) or "raw_db.source_table"
    target_table = _maybe_table(tgt_raw) or _maybe_table(str(d.get("target_table") or "")) or "curated_db.target_table"

    if not src_raw and "source_table" not in d:
        warnings.append(ParseWarning("source_table.missing", f"source_table missing; defaulted to {source_table}"))
        explain["defaults_used"].append(f"source_table={source_table}")
    if src_raw and not _maybe_table(src_raw):
        warnings.append(ParseWarning("source_table.invalid", f"source_table '{src_raw}' not in db.table format; defaulted to {source_table}"))
        explain["normalizations"].append({"field": "source_table", "from": src_raw, "to": source_table})

    if not tgt_raw and "target_table" not in d:
        warnings.append(ParseWarning("target_table.missing", f"target_table missing; defaulted to {target_table}"))
        explain["defaults_used"].append(f"target_table={target_table}")
    if tgt_raw and not _maybe_table(tgt_raw):
        warnings.append(ParseWarning("target_table.invalid", f"target_table '{tgt_raw}' not in db.table format; defaulted to {target_table}"))
        explain["normalizations"].append({"field": "target_table", "from": tgt_raw, "to": target_table})

    # --- partition column ---
    part_raw = _first_match(_PAT_PARTITION_COL, text)
    explain["matches"]["partition_column_raw"] = part_raw or None
    partition_column = (part_raw or str(d.get("partition_column") or "data_dt")).strip() or "data_dt"
    if not part_raw and "partition_column" not in d:
        explain["defaults_used"].append(f"partition_column={partition_column}")

    # --- write mode ---
    wm_raw = _first_match(_PAT_WRITE_MODE, text)
    explain["matches"]["write_mode_raw"] = wm_raw or None
    write_mode = _pick_enum(wm_raw, ("merge", "append", "overwrite")) or str(d.get("write_mode") or "merge").lower()
    if write_mode not in ("merge", "append", "overwrite"):
        warnings.append(ParseWarning("write_mode.invalid", f"write_mode '{write_mode}' not recognized; defaulted to 'merge'"))
        explain["defaults_used"].append("write_mode=merge")
        write_mode = "merge"
    if not wm_raw and "write_mode" not in d:
        explain["defaults_used"].append(f"write_mode={write_mode}")

    # --- spark settings ---
    spark_dynamic_allocation = bool(d.get("spark_dynamic_allocation", True))
    spark_conf_overrides = d.get("spark_conf_overrides", {}) or {}
    if not isinstance(spark_conf_overrides, dict):
        warnings.append(ParseWarning("spark_conf_overrides.invalid", "spark_conf_overrides must be a dict; defaulted to {}"))
        explain["defaults_used"].append("spark_conf_overrides={}")
        spark_conf_overrides = {}
    if "spark_dynamic_allocation" not in d:
        explain["defaults_used"].append(f"spark_dynamic_allocation={spark_dynamic_allocation}")
    if "spark_conf_overrides" not in d:
        explain["defaults_used"].append("spark_conf_overrides=defaults/{}")

    # --- optional milestone flags ---
    dq_enabled = bool(d.get("dq_enabled", False))
    troubleshoot_enabled = bool(d.get("troubleshoot_enabled", False))

    spec: Dict[str, Any] = {
        # required identity
        "job_name": job_name,
        "preset": preset,

        # runtime / schedule
        "owner": owner,
        "env": env,
        "schedule": schedule,
        "timezone": timezone,
        "description": description,
        "tags": tags,

        # IO
        "source_table": source_table,
        "target_table": target_table,
        "partition_column": partition_column,
        "write_mode": write_mode,

        # language
        "language": language,

        # spark
        "spark_dynamic_allocation": spark_dynamic_allocation,
        "spark_conf_overrides": spark_conf_overrides,

        # future hooks
        "dq_enabled": dq_enabled,
        "troubleshoot_enabled": troubleshoot_enabled,
    }

    # ----------------------------
    # Confidence (simple, stable)
    # - 1.0 means no warnings
    # - downweight by #warnings
    # - clamp to [0.5, 1.0]
    # ----------------------------
    confidence = 1.0 - (0.1 * len(warnings))
    confidence = max(0.5, min(1.0, round(confidence, 2)))

    explain["summary"] = {
        "warning_count": len(warnings),
        "confidence": confidence,
    }

    return ParseResult(spec=spec, warnings=warnings, confidence=confidence, explain=explain)
