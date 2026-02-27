import json
import logging
import logging.handlers
import time
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_AUDIT_PATH = Path(".copilot") / "audit.log"

# Fix 12: RotatingFileHandler — 10MB max per file, 5 backups
_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_BACKUP_COUNT = 5

_handler_cache: Dict[str, logging.Handler] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_rotating_handler(audit_path: Path) -> logging.Handler:
    key = str(audit_path.resolve())
    if key not in _handler_cache:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(
            str(audit_path),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        h.setFormatter(logging.Formatter("%(message)s"))
        _handler_cache[key] = h
    return _handler_cache[key]


def audit_event(
    event_type: str,
    request_id: Optional[str],
    actor: Optional[str],
    tenant: Optional[str],
    method: Optional[str],
    path: Optional[str],
    status_code: Optional[int],
    extra: Optional[Dict[str, Any]] = None,
    audit_path: Path = DEFAULT_AUDIT_PATH,
) -> None:
    record: Dict[str, Any] = {
        "ts_ms": _now_ms(),
        "type": event_type,
        "request_id": request_id,
        "actor": actor,
        "tenant": tenant,
        "http": {
            "method": method,
            "path": path,
            "status": status_code,
        },
    }
    if extra:
        record["extra"] = extra

    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)

    handler = _get_rotating_handler(audit_path)
    log_record = logging.LogRecord(
        name="copilot.audit",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=line,
        args=(),
        exc_info=None,
    )
    handler.emit(log_record)