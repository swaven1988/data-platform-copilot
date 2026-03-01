import hashlib
import fnmatch
import json
import subprocess
import tarfile
from pathlib import Path
from datetime import datetime, timezone


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "packaging_manifest.json"

EXTRA_EXCLUDE_PATTERNS = [
    "**/__pycache__/**",
    "**/*.pyc",
    "**/.pytest_cache/**",
    "**/.venv/**",
    "**/dist/**",
    "**/knowledge_base/**",
    "**/mkdir/**",
    "**/*.bak",
    "**/*.bkp",
    "**/*.log",
    "**/nul",
    "**/-H",
    "**/-d",
    "**/.git/**",
    "**/workspace/**",
    # Node / frontend build artifacts
    "**/node_modules/**",
    "frontend/.vite/**",
    # Agent working documents — not source
    "antigravity_prompt*.md",
    # Secret credential files
    "deploy/secrets/*.txt",
    # Defensive exclusion for legacy bootstrap scripts
    "install.cmd",
]


def _is_excluded(rel_path: str, patterns: list[str] | None = None) -> bool:
    p = rel_path.replace("\\", "/")
    pats = patterns or EXTRA_EXCLUDE_PATTERNS
    # Match both plain relative path and slash-prefixed form so patterns like
    # "**/.venv/**" also match root-level ".venv/..." paths consistently.
    return any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(f"/{p}", pat) for pat in pats)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git_info():
    def run(cmd):
        return subprocess.check_output(cmd, cwd=REPO_ROOT).decode().strip()

    try:
        tag = run(["git", "describe", "--tags", "--abbrev=0"])
    except Exception:
        tag = "untagged"

    try:
        commit = run(["git", "rev-parse", "HEAD"])
    except Exception:
        commit = "unknown"

    return tag, commit


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise RuntimeError("packaging_manifest.json not found")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def normalize_manifest_files(manifest: dict) -> list[str]:
    """
    Supports:
      - files: ["path/a", "path/b"]
      - files: [{"path":"path/a","sha256":"..."}, ...]
    """
    files = manifest.get("files", [])
    out: list[str] = []
    for item in files:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            p = item.get("path") or item.get("file") or item.get("name")
            if isinstance(p, str) and p:
                out.append(p)
    # stable + unique
    return sorted(set(out))


def build_tar(files: list[str], output_path: Path, *, exclude_patterns: list[str]):
    def _tarinfo_filter(ti: tarfile.TarInfo) -> tarfile.TarInfo:
        # deterministic-ish metadata
        ti.uid = 0
        ti.gid = 0
        ti.uname = ""
        ti.gname = ""
        ti.mtime = 0
        return ti

    with tarfile.open(output_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for rel in files:
            if _is_excluded(rel, exclude_patterns):
                continue
            abs_path = REPO_ROOT / rel
            if abs_path.exists():
                tar.add(abs_path, arcname=rel, filter=_tarinfo_filter)


def main():
    manifest = load_manifest()
    manifest_excludes = list(manifest.get("excludes") or [])
    exclude_patterns = sorted(set(manifest_excludes + EXTRA_EXCLUDE_PATTERNS))
    files = normalize_manifest_files(manifest)

    tag, commit = get_git_info()
    artifact_name = f"data-platform-copilot-{tag}.tar.gz"
    artifact_path = REPO_ROOT / artifact_name

    print(f"Building release artifact: {artifact_name}")
    build_tar(files, artifact_path, exclude_patterns=exclude_patterns)

    sha = sha256_file(artifact_path)

    metadata = {
        "project": "data-platform-copilot",
        "tag": tag,
        "commit": commit,
        "artifact": artifact_name,
        "sha256": sha,
        "built_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "file_count": len(files),
    }

    metadata_path = REPO_ROOT / "release_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    print("Release artifact built successfully.")
    print(f"SHA256: {sha}")
    print(f"Metadata written to: {metadata_path}")


if __name__ == "__main__":
    main()
