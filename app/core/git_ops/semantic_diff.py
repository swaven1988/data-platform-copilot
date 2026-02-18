from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.core.git_ops.repo_manager import _run_git


def _git_show(repo_path: Path, ref: str, file_path: str) -> str:
    rc, out, err = _run_git(repo_path, ["show", f"{ref}:{file_path}"])
    if rc != 0:
        return ""
    return out or ""


def _name_status(repo_path: Path, ref_a: str, ref_b: str, paths: Optional[List[str]]) -> List[Tuple[str, str]]:
    args = ["diff", "--name-status", f"{ref_a}..{ref_b}"]
    if paths:
        args += ["--", *paths]
    rc, out, err = _run_git(repo_path, args)
    if rc != 0:
        raise RuntimeError(err or out)
    rows: List[Tuple[str, str]] = []
    for line in (out.splitlines() if out else []):
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0].strip(), parts[1].strip()))
    return rows


def _json_diff(a: Any, b: Any, prefix: str = "") -> Dict[str, Any]:
    changes = {"added": [], "removed": [], "modified": []}

    if isinstance(a, dict) and isinstance(b, dict):
        a_keys = set(a.keys())
        b_keys = set(b.keys())
        for k in sorted(b_keys - a_keys):
            changes["added"].append(prefix + k)
        for k in sorted(a_keys - b_keys):
            changes["removed"].append(prefix + k)
        for k in sorted(a_keys & b_keys):
            sub_a, sub_b = a[k], b[k]
            p = prefix + k + "."
            sub = _json_diff(sub_a, sub_b, p)
            for typ in ("added", "removed", "modified"):
                changes[typ].extend(sub[typ])
        return changes

    if isinstance(a, list) and isinstance(b, list):
        if a != b:
            changes["modified"].append(prefix.rstrip(".") or "$")
        return changes

    if a != b:
        changes["modified"].append(prefix.rstrip(".") or "$")
    return changes


def _python_ast_summary(src: str) -> Dict[str, Any]:
    try:
        t = ast.parse(src or "")
    except Exception:
        return {"parseable": False, "imports": [], "defs": []}

    imports: List[str] = []
    defs: List[str] = []

    for node in ast.walk(t):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for n in node.names:
                imports.append(f"{mod}:{n.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            defs.append(f"{node.name}({', '.join(args)})")
        elif isinstance(node, ast.ClassDef):
            defs.append(f"class {node.name}")

    return {"parseable": True, "imports": sorted(set(imports)), "defs": sorted(set(defs))}


def semantic_diff(repo_path: Path, *, ref_a: str, ref_b: str, paths: Optional[List[str]] = None) -> Dict[str, Any]:
    rows = _name_status(repo_path, ref_a, ref_b, paths)

    files: List[Dict[str, Any]] = []
    for status, fp in rows:
        ext = Path(fp).suffix.lower()
        before = _git_show(repo_path, ref_a, fp) if status != "A" else ""
        after = _git_show(repo_path, ref_b, fp) if status != "D" else ""

        entry: Dict[str, Any] = {"path": fp, "status": status, "semantic": {}}

        if ext in (".json",):
            try:
                a_obj = json.loads(before) if before else None
                b_obj = json.loads(after) if after else None
                if a_obj is None or b_obj is None:
                    entry["semantic"]["json"] = {"parseable": False}
                else:
                    entry["semantic"]["json"] = {"parseable": True, **_json_diff(a_obj, b_obj, "")}
            except Exception:
                entry["semantic"]["json"] = {"parseable": False}

        elif ext in (".yml", ".yaml"):
            try:
                a_obj = yaml.safe_load(before) if before else None
                b_obj = yaml.safe_load(after) if after else None
                if a_obj is None or b_obj is None:
                    entry["semantic"]["yaml"] = {"parseable": False}
                else:
                    entry["semantic"]["yaml"] = {"parseable": True, **_json_diff(a_obj, b_obj, "")}
            except Exception:
                entry["semantic"]["yaml"] = {"parseable": False}

        elif ext == ".py":
            entry["semantic"]["python"] = {
                "before": _python_ast_summary(before),
                "after": _python_ast_summary(after),
            }

        elif ext in (".md", ".markdown"):
            def headers(txt: str) -> List[str]:
                hs=[]
                for line in (txt.splitlines() if txt else []):
                    if line.lstrip().startswith("#"):
                        hs.append(line.strip())
                return hs
            entry["semantic"]["markdown"] = {
                "before_headers": headers(before),
                "after_headers": headers(after),
            }

        files.append(entry)

    return {
        "ref_a": ref_a,
        "ref_b": ref_b,
        "scoped_paths": paths or [],
        "files": files,
        "file_count": len(files),
    }
