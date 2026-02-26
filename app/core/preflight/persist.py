# app/core/preflight/persist.py

import os
import json
from .models import PreflightReport


def persist_report(report: PreflightReport, base_path: str = ".") -> str:
    path = os.path.join(base_path, ".copilot", "preflight")
    os.makedirs(path, exist_ok=True)

    file_path = os.path.join(path, f"{report.preflight_hash}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(report.dict(), f, indent=2)

    return file_path


def load_report(job_name: str, preflight_hash: str, base_path: str = "."):
    file_path = os.path.join(base_path, ".copilot", "preflight", f"{preflight_hash}.json")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)