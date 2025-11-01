from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class FetchResult:
    repo_url: str
    dest_path: str
    branch: Optional[str]
    sha: Optional[str]
    resolved_commit: str
    default_branch: Optional[str]
    fetched_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {shlex.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc


def slugify_repo(url_or_path: str) -> str:
    # If local path, use basename
    p = Path(url_or_path)
    if p.exists():
        name = p.name
    else:
        # Strip schema
        s = re.sub(r"^[a-zA-Z]+://", "", url_or_path)
        # Remove .git suffix
        s = re.sub(r"\.git$", "", s)
        parts = [x for x in re.split(r"[/:@]+", s) if x]
        if len(parts) >= 2:
            name = f"{parts[-2]}__{parts[-1]}"
        else:
            name = parts[-1] if parts else "repo"
    # Sanitize
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def clone_or_update(url_or_path: str, dest_root: Path, *, shallow_depth: int = 1) -> Path:
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / slugify_repo(url_or_path)
    if not is_git_repo(dest):
        # Clone
        cmd = ["git", "clone"]
        if shallow_depth and shallow_depth > 0:
            cmd += ["--depth", str(shallow_depth)]
        cmd += [url_or_path, str(dest)]
        _run(cmd)
    else:
        # Fetch updates best-effort
        try:
            _run(["git", "fetch", "--all", "--prune"], cwd=dest)
        except Exception:
            pass
    return dest


def get_current_commit(repo_path: Path) -> str:
    proc = _run(["git", "rev-parse", "HEAD"], cwd=repo_path)
    return proc.stdout.strip()


def get_default_branch(repo_path: Path) -> Optional[str]:
    # Try to resolve origin/HEAD -> origin/<branch>
    try:
        proc = _run(["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], cwd=repo_path, check=False)
        ref = proc.stdout.strip()
        if ref.startswith("origin/"):
            return ref.split("/", 1)[1]
    except Exception:
        return None
    return None


def checkout(repo_path: Path, *, branch: Optional[str] = None, sha: Optional[str] = None, shallow_depth: int = 1) -> str:
    if sha:
        # Ensure commit exists locally
        fetched = False
        try:
            _run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo_path)
            fetched = True
        except Exception:
            # Try shallow fetch of exact commit
            try:
                _run(["git", "fetch", "origin", sha, "--depth", str(max(1, shallow_depth))], cwd=repo_path)
                fetched = True
            except Exception:
                # Fallback to full fetch
                _run(["git", "fetch", "--all", "--tags"], cwd=repo_path)
                fetched = True
        if fetched:
            _run(["git", "checkout", "--detach", sha], cwd=repo_path)
            return get_current_commit(repo_path)

    if branch:
        # Fetch branch tip shallowly
        try:
            _run(["git", "fetch", "origin", branch, "--depth", str(max(1, shallow_depth))], cwd=repo_path)
        except Exception:
            _run(["git", "fetch", "origin", branch], cwd=repo_path)
        # Reset to remote tracking
        # Create or switch local branch tracking origin/branch
        _run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=repo_path)
        return get_current_commit(repo_path)

    # No specific target: stay on current HEAD
    return get_current_commit(repo_path)


def write_manifest(repo_path: Path, manifest_path: Path, info: Dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(info)
    data["resolved_commit"] = info.get("resolved_commit")
    data["dest_path"] = str(repo_path)
    data["fetched_at"] = _now_iso()
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_repo(url_or_path: str, *, out_root: Path, branch: Optional[str] = None, sha: Optional[str] = None, depth: int = 1) -> FetchResult:
    repo_path = clone_or_update(url_or_path, out_root, shallow_depth=depth)
    resolved = checkout(repo_path, branch=branch, sha=sha, shallow_depth=depth)
    dflt = get_default_branch(repo_path)
    return FetchResult(
        repo_url=url_or_path,
        dest_path=str(repo_path),
        branch=branch,
        sha=sha,
        resolved_commit=resolved,
        default_branch=dflt,
        fetched_at=_now_iso(),
    )

