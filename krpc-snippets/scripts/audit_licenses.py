#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any


def _load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _is_gpl_family(spdx: str) -> bool:
    s = (spdx or "").upper()
    return any(x in s for x in ("GPL", "AGPL", "LGPL"))


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Audit snippet licenses and provenance; optionally fail on violations")
    p.add_argument("--snippets", required=True, help="Snippets JSONL to audit")
    p.add_argument("--report", help="Write detailed JSON report to this path")
    p.add_argument("--fail-on-unknown", action="store_true", help="Exit non-zero if any license is UNKNOWN/empty")
    p.add_argument("--fail-on-restricted", action="store_true", help="Exit non-zero if any restricted (GPL family) are present")
    p.add_argument("--fail-on-mismatch", action="store_true", help="Exit non-zero if restricted flag mismatches SPDX inference")

    args = p.parse_args(argv)
    path = Path(args.snippets)
    recs = _load_jsonl(path)

    by_license: dict[str, int] = {}
    restricted_ids: list[str] = []
    unknown_ids: list[str] = []
    mismatched: list[str] = []
    missing_prov: list[str] = []

    for r in recs:
        rid = str(r.get("id"))
        lic = (r.get("license") or "").strip()
        by_license[lic or "UNKNOWN"] = by_license.get(lic or "UNKNOWN", 0) + 1
        if not lic or lic.upper() == "UNKNOWN":
            unknown_ids.append(rid)
        inferred_restricted = _is_gpl_family(lic)
        declared_restricted = bool(r.get("restricted")) if r.get("restricted") is not None else inferred_restricted
        if declared_restricted:
            restricted_ids.append(rid)
        if inferred_restricted != declared_restricted:
            mismatched.append(rid)
        # Provenance
        if not (r.get("repo") and r.get("commit") and r.get("path")):
            missing_prov.append(rid)

    summary: Dict[str, Any] = {
        "total": len(recs),
        "by_license": by_license,
        "restricted_count": len(restricted_ids),
        "unknown_count": len(unknown_ids),
        "mismatched_restricted": len(mismatched),
        "missing_provenance": len(missing_prov),
    }

    print(json.dumps(summary, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps({
            **summary,
            "restricted_ids": restricted_ids,
            "unknown_ids": unknown_ids,
            "mismatched_ids": mismatched,
            "missing_provenance_ids": missing_prov,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    exit_code = 0
    if args.fail_on_unknown and unknown_ids:
        exit_code = 2
    if args.fail_on_restricted and restricted_ids:
        exit_code = max(exit_code, 3)
    if args.fail_on_mismatch and mismatched:
        exit_code = max(exit_code, 4)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

