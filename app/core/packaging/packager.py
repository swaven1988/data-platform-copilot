import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def make_zip(job_name: str, files: Dict[str, str]) -> str:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    zip_path = OUTPUTS_DIR / f"{job_name}_{ts}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, content in files.items():
            zf.writestr(rel_path, content)

    return str(zip_path)
