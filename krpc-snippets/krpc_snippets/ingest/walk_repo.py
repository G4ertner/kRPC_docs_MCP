from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


REPO_IGNORE_FILE = ".krpc-snippets-ignore"


@dataclass
class FileInfo:
    repo_root: str
    rel_path: str
    abs_path: str
    lang: str
    size_bytes: int
    sha256: str


@dataclass
class WalkOptions:
    include_globs: List[str] = field(default_factory=lambda: ["**/*.py"])
    exclude_dirs: List[str] = field(default_factory=lambda: default_exclude_dirs())
    exclude_globs: List[str] = field(default_factory=list)
    max_size_bytes: Optional[int] = None
    use_git_ls_files: bool = True


def default_exclude_dirs() -> List[str]:
    return [
        ".git", ".hg", ".svn",
        "__pycache__", ".idea", ".vscode",
        ".tox", ".mypy_cache", ".pytest_cache",
        ".venv", "venv", "env",
        "build", "dist",
        "site-packages", "node_modules",
        "vendor", "third_party",
    ]


def _read_repo_ignores(repo_root: Path) -> List[str]:
    path = repo_root / REPO_IGNORE_FILE
    if not path.exists():
        return []
    patterns: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        patterns.append(s)
    return patterns


def _git_ls_files(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        text=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    raw = proc.stdout or b""
    # NUL separated
    items = [s.decode("utf-8", errors="ignore") for s in raw.split(b"\x00") if s]
    return [x for x in items if x]


def _match_any(path: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        # Interpret patterns as glob, applied on POSIX-style rel_path
        if fnmatch.fnmatch(path, pat):
            return True
        # Additional support for directory-wide patterns like '**/pkg/**' or 'pkg/**'
        if "/**" in pat:
            base = pat.split("/**", 1)[0]
            # strip leading '**/' if present
            while base.startswith("**/"):
                base = base[3:]
            if not base:
                continue
            if path == base or path.startswith(base + "/") or ("/" + base + "/") in ("/" + path + "/"):
                return True
    return False


def _sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_excluded_dir(name: str, exclude_dirs: Iterable[str]) -> bool:
    return name in set(exclude_dirs)


def discover_python_files(repo_root: Path, opts: Optional[WalkOptions] = None) -> List[FileInfo]:
    opts = opts or WalkOptions()
    repo_root = repo_root.resolve()

    # Merge repo-level excludes
    repo_excludes = _read_repo_ignores(repo_root)
    exclude_globs = list(opts.exclude_globs) + repo_excludes

    rel_paths: List[str] = []
    used_git = False

    if opts.use_git_ls_files and (repo_root / ".git").exists():
        rel_paths = _git_ls_files(repo_root)
        used_git = bool(rel_paths)

    if not used_git:
        # Walk filesystem
        for root, dirs, files in os.walk(repo_root):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if not _is_excluded_dir(d, opts.exclude_dirs)]
            for fn in files:
                rel = str(Path(root, fn).resolve().relative_to(repo_root))
                rel_paths.append(rel)

    # Normalize to POSIX-style
    rel_paths = [rel.replace("\\", "/") for rel in rel_paths]
    # Apply include globs
    included = [rel for rel in rel_paths if _match_any(rel, opts.include_globs)]
    # Apply exclude globs
    if exclude_globs:
        included = [rel for rel in included if not _match_any(rel, exclude_globs)]

    out: List[FileInfo] = []
    for rel in included:
        abs_p = (repo_root / rel).resolve()
        try:
            st = abs_p.stat()
        except Exception:
            continue
        size = int(st.st_size)
        if opts.max_size_bytes is not None and size > int(opts.max_size_bytes):
            continue
        try:
            digest = _sha256_of_file(abs_p)
        except Exception:
            continue
        out.append(FileInfo(
            repo_root=str(repo_root),
            rel_path=rel,
            abs_path=str(abs_p),
            lang="python",
            size_bytes=size,
            sha256=digest,
        ))

    # Deterministic order
    out.sort(key=lambda fi: fi.rel_path)
    return out


def to_jsonl(items: Iterable[FileInfo]) -> str:
    lines = []
    for it in items:
        lines.append(json.dumps(it.__dict__, ensure_ascii=False))
    return "\n".join(lines)
