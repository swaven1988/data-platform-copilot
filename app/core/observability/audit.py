import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_AUDIT_PATH = Path(".copilot") / "audit.log"


def _now_ms() -> int:
    return int(time.time() * 1000)


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
    audit_path.parent.mkdir(parents=True, exist_ok=True)

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

    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")