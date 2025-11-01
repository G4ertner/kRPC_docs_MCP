from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from .python_ast import parse_python_module
from .extract_snippets import stable_id


@dataclass
class AuditReport:
    missing_provenance: bool
    bad_path: bool
    id_mismatch: bool
    span_unresolved: bool
    proposed_id: Optional[str]


def read_fetch_manifest(repo_root: Path) -> Optional[Dict[str, str]]:
    """Read fetch.json if present at repo root (from B1)."""
    for candidate in (repo_root / "fetch.json",):
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return {
                    "repo_url": data.get("repo_url"),
                    "commit": data.get("resolved_commit"),
                }
            except Exception:
                return None
    return None


def normalize_repo_url(url: Optional[str]) -> Optional[str]:
    if url is None:
        return None
    return url.strip()


def normalize_path(repo_root: Path, rel_path: str | Path) -> str:
    """Return POSIX-style repo-relative path and ensure it resides under repo_root."""
    repo_root = repo_root.resolve()
    p = (repo_root / rel_path).resolve()
    rel = p.relative_to(repo_root)
    return str(rel).replace("\\", "/")


def fill_provenance(record: Dict, repo_root: Path, repo_url: Optional[str], commit: Optional[str]) -> Dict:
    out = dict(record)
    # Path normalization
    try:
        out["path"] = normalize_path(repo_root, out.get("path", ""))
        bad_path = False
    except Exception:
        bad_path = True
    # Repo/commit
    if not repo_url or not commit:
        det = read_fetch_manifest(repo_root) or {}
        repo_url = repo_url or det.get("repo_url")
        commit = commit or det.get("commit")
    if repo_url and not out.get("repo"):
        out["repo"] = normalize_repo_url(repo_url)
    if commit and not out.get("commit"):
        out["commit"] = str(commit)
    return out


def _find_node_span_for_record(repo_root: Path, record: Dict) -> Optional[Tuple[str, str, int, int]]:
    """Return (kind, qualname, lineno, end_lineno) for a record by parsing the module and matching name/kind.

    Uses record['name'] and record['categories'][0] to select kind, then finds a unique match.
    For const block, uses the first const block.
    """
    rel = record.get("path")
    kind = (record.get("categories") or ["function"])[0]
    name = record.get("name")
    fp = (repo_root / rel).resolve()
    mod = parse_python_module(fp)
    if mod.parse_error:
        return None
    if kind == "function":
        for fn in mod.functions:
            if fn.qualname == name:
                return (kind, fn.qualname, fn.lineno, fn.end_lineno)
    elif kind == "method":
        # Methods are stored under classes in summary
        for cls in mod.classes:
            for m in cls.methods:
                if m.qualname == name:
                    return (kind, m.qualname, m.lineno, m.end_lineno)
    elif kind == "class":
        for cls in mod.classes:
            if cls.qualname == name:
                return (kind, cls.qualname, cls.lineno, cls.end_lineno)
    elif kind == "const":
        cb = (mod.const_blocks[0] if mod.const_blocks else None)
        if cb is not None:
            return (kind, "CONST_BLOCK", cb.lineno, cb.end_lineno)
    return None


def recompute_id(record: Dict, repo_root: Path) -> Optional[str]:
    repo = record.get("repo")
    commit = record.get("commit")
    rel = record.get("path")
    if not (repo and commit and rel):
        return None
    span = _find_node_span_for_record(repo_root, record)
    if not span:
        return None
    kind, qualname, lineno, end_lineno = span
    return stable_id(str(repo), str(commit), str(rel), kind, qualname, lineno, end_lineno)


def audit_record(record: Dict, repo_root: Path, repo_url: Optional[str], commit: Optional[str]) -> AuditReport:
    missing_prov = not bool(record.get("repo")) or not bool(record.get("commit"))
    # Path validity
    try:
        normalize_path(repo_root, record.get("path", ""))
        bad_path = False
    except Exception:
        bad_path = True
    new_id = recompute_id(record, repo_root)
    id_mismatch = False
    span_unresolved = False
    if new_id is None:
        span_unresolved = True
    else:
        id_mismatch = (str(record.get("id")) != new_id)
    return AuditReport(
        missing_provenance=missing_prov,
        bad_path=bad_path,
        id_mismatch=id_mismatch,
        span_unresolved=span_unresolved,
        proposed_id=new_id,
    )


def fix_record(record: Dict, repo_root: Path, repo_url: Optional[str], commit: Optional[str], *, repair_id: bool = False) -> Dict:
    out = fill_provenance(record, repo_root, repo_url, commit)
    if repair_id:
        new_id = recompute_id(out, repo_root)
        if new_id:
            out["id"] = new_id
    return out


def build_provenance_map(snippets: List[Dict]) -> List[Dict]:
    out = []
    for r in snippets:
        out.append({
            "id": r.get("id"),
            "repo": r.get("repo"),
            "commit": r.get("commit"),
            "path": r.get("path"),
            "created_at": r.get("created_at"),
        })
    return out

