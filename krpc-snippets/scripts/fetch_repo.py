#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from krpc_snippets.ingest.git_fetch import fetch_repo, slugify_repo, write_manifest


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Fetch and cache repositories for krpc-snippets ingestion")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", dest="url", help="Repository URL or local path")
    g.add_argument("--file", dest="file", help="JSONL file of {url,branch?,sha?}")
    p.add_argument("--branch", dest="branch", default=None)
    p.add_argument("--sha", dest="sha", default=None)
    p.add_argument("--depth", dest="depth", type=int, default=1)
    p.add_argument("--out", dest="out", default="krpc-snippets/data/repos")

    args = p.parse_args(argv)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    tasks: List[Dict[str, Any]] = []
    if args.url:
        tasks.append({"url": args.url, "branch": args.branch, "sha": args.sha, "depth": args.depth})
    else:
        tasks = _load_jsonl(Path(args.file))

    ok = True
    for t in tasks:
        url = t.get("url")
        if not url:
            print("SKIP: missing url in task")
            ok = False
            continue
        branch = t.get("branch") or None
        sha = t.get("sha") or None
        depth = int(t.get("depth") or args.depth)
        try:
            res = fetch_repo(url, out_root=out_root, branch=branch, sha=sha, depth=depth)
            slug = slugify_repo(url)
            manifest_path = out_root / slug / "fetch.json"
            write_manifest(Path(res.dest_path), manifest_path, {
                "repo_url": res.repo_url,
                "branch": res.branch,
                "sha": res.sha,
                "resolved_commit": res.resolved_commit,
                "default_branch": res.default_branch,
            })
            print(json.dumps({
                "url": url,
                "dest": res.dest_path,
                "commit": res.resolved_commit,
                "manifest": str(manifest_path),
            }))
        except Exception as e:
            ok = False
            print(f"ERROR fetching {url}: {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

