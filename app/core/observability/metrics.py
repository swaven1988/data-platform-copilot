from collections import Counter
from typing import Dict

_REQUESTS = Counter()


def inc_request(path: str, status: int | None):
    key = f"{path}|{status if status is not None else 'unknown'}"
    _REQUESTS[key] += 1


def snapshot() -> Dict[str, int]:
    return dict(_REQUESTS)