from dataclasses import dataclass
from typing import List, Optional
import subprocess


@dataclass
class DiffContext:
    changed_files: List[str]
    added: List[str]
    modified: List[str]
    deleted: List[str]
    git_error: Optional[str] = None


class DiffAnalyzer:

    @staticmethod
    def get_changed_files(base_ref: str = "upstream/main", repo_dir: str | None = None) -> DiffContext:
        cmd = ["git"]
        if repo_dir:
            cmd += ["-C", repo_dir]
        cmd += ["diff", "--name-status", base_ref]

        try:
            r = subprocess.run(cmd, capture_output=True, text=True)

            if r.returncode != 0:
                return DiffContext(
                    changed_files=[],
                    added=[],
                    modified=[],
                    deleted=[],
                    git_error=(r.stderr or r.stdout or "").strip() or f"git diff failed for {base_ref}",
                )

            lines = (r.stdout or "").strip().split("\n")
            added, modified, deleted = [], [], []

            for line in lines:
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue
                status, path = parts
                if status == "A":
                    added.append(path)
                elif status == "M":
                    modified.append(path)
                elif status == "D":
                    deleted.append(path)

            return DiffContext(
                changed_files=added + modified + deleted,
                added=added,
                modified=modified,
                deleted=deleted,
                git_error=None,
            )

        except Exception as e:
            return DiffContext(
                changed_files=[],
                added=[],
                modified=[],
                deleted=[],
                git_error=str(e),
            )
