from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, List


# Canonical SPDX -> canonical URL mapping (subset sufficient for this project)
SPDX_URL: Dict[str, str] = {
    "MIT": "https://opensource.org/licenses/MIT",
    "Apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
    "BSD-2-Clause": "https://opensource.org/licenses/BSD-2-Clause",
    "BSD-3-Clause": "https://opensource.org/licenses/BSD-3-Clause",
    "GPL-2.0": "https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html",
    "GPL-3.0": "https://www.gnu.org/licenses/gpl-3.0-standalone.html",
    "AGPL-3.0": "https://www.gnu.org/licenses/agpl-3.0-standalone.html",
    "LGPL-2.1": "https://www.gnu.org/licenses/old-licenses/lgpl-2.1-standalone.html",
    "LGPL-3.0": "https://www.gnu.org/licenses/lgpl-3.0-standalone.html",
    "MPL-2.0": "https://www.mozilla.org/MPL/2.0/",
    "Unlicense": "https://unlicense.org/",
    "ISC": "https://opensource.org/licenses/ISC",
}


def _normalize_spdx(spdx_id: str) -> str:
    s = spdx_id.strip()
    s = s.replace("-only", "").replace("-or-later", "")
    # Common normalizations
    replacements = {
        "GPL-3.0+": "GPL-3.0",
        "GPL-3.0-only": "GPL-3.0",
        "GPL-3.0-or-later": "GPL-3.0",
        "GPL-2.0+": "GPL-2.0",
        "GPL-2.0-only": "GPL-2.0",
        "GPL-2.0-or-later": "GPL-2.0",
        "LGPL-3.0+": "LGPL-3.0",
        "LGPL-2.1+": "LGPL-2.1",
    }
    s = replacements.get(s, s)
    return s


def _is_restricted(spdx_id: str) -> bool:
    s = spdx_id.upper()
    return any(x in s for x in ("GPL", "AGPL", "LGPL"))


LICENSE_FILENAMES = [
    "LICENSE", "LICENSE.txt", "LICENSE.md",
    "COPYING", "COPYING.txt",
    "LICENCE", "LICENCE.txt",  # alternate spelling
]


HEURISTICS: List[Tuple[str, str]] = [
    (r"Permission is hereby granted, free of charge", "MIT"),
    (r"Apache License, Version\s*2\.0", "Apache-2.0"),
    (r"Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:", "BSD-3-Clause"),
    (r"GNU GENERAL PUBLIC LICENSE\s*Version\s*3", "GPL-3.0"),
    (r"GNU GENERAL PUBLIC LICENSE\s*Version\s*2", "GPL-2.0"),
    (r"GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0"),
    (r"Mozilla Public License,? version 2\.0", "MPL-2.0"),
    (r"This is free and unencumbered software released into the public domain", "Unlicense"),
    (r"Permission to use, copy, modify, and/or distribute", "ISC"),
]


SPDX_HEADER_RE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9+\.-]+)")


@dataclass
class LicenseInfo:
    spdx_id: str
    name: str
    url: str
    restricted: bool
    source: str
    file_path: Optional[str] = None


def detect_spdx_in_header(file_path: Path, max_lines: int = 20) -> Optional[str]:
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for i in range(max_lines):
                line = f.readline()
                if not line:
                    break
                m = SPDX_HEADER_RE.search(line)
                if m:
                    return _normalize_spdx(m.group(1))
    except Exception:
        return None
    return None


def _detect_from_license_files(repo_root: Path) -> Optional[LicenseInfo]:
    # Case-insensitive search of common license filenames at repo root
    files = {p.name.lower(): p for p in repo_root.glob("*") if p.is_file()}
    chosen: Optional[Path] = None
    for name in LICENSE_FILENAMES:
        p = files.get(name.lower())
        if p is not None:
            chosen = p
            break
    if not chosen:
        return None
    text = chosen.read_text(encoding="utf-8", errors="ignore")
    # Try SPDX line
    m = SPDX_HEADER_RE.search(text)
    if m:
        spdx = _normalize_spdx(m.group(1))
        url = SPDX_URL.get(spdx, "")
        return LicenseInfo(spdx_id=spdx, name=spdx, url=url, restricted=_is_restricted(spdx), source="LICENSE_FILE", file_path=str(chosen))
    # Heuristics
    for pattern, spdx in HEURISTICS:
        if re.search(pattern, text, flags=re.I | re.S):
            spdx = _normalize_spdx(spdx)
            url = SPDX_URL.get(spdx, "")
            return LicenseInfo(spdx_id=spdx, name=spdx, url=url, restricted=_is_restricted(spdx), source="HEURISTIC", file_path=str(chosen))
    return LicenseInfo(spdx_id="UNKNOWN", name="UNKNOWN", url="", restricted=False, source="UNKNOWN", file_path=str(chosen))


def detect_repo_license(repo_root: Path) -> LicenseInfo:
    repo_root = repo_root.resolve()
    # 1) License file
    lic = _detect_from_license_files(repo_root)
    if lic is not None and lic.spdx_id != "UNKNOWN":
        return lic
    # 2) SPDX headers in tracked Python files (best-effort; scan a subset)
    py_files = list(repo_root.rglob("*.py"))[:200]  # cap for performance
    for fp in py_files:
        spdx = detect_spdx_in_header(fp)
        if spdx:
            url = SPDX_URL.get(spdx, "")
            return LicenseInfo(spdx_id=spdx, name=spdx, url=url, restricted=_is_restricted(spdx), source="SPDX_HEADER", file_path=str(fp.relative_to(repo_root)))
    # 3) Unknown
    return LicenseInfo(spdx_id="UNKNOWN", name="UNKNOWN", url="", restricted=False, source="UNKNOWN")


def summarize_repo_license(repo_root: Path) -> Dict[str, object]:
    lic = detect_repo_license(repo_root)
    # spdx coverage among files
    total_py = 0
    spdx_hits = 0
    for fp in repo_root.rglob("*.py"):
        total_py += 1
        if detect_spdx_in_header(fp):
            spdx_hits += 1
    return {
        "license": lic.__dict__,
        "spdx_headers": {"files_with_spdx": spdx_hits, "total_py_files": total_py},
    }


def enrich_snippets_with_license(snippets: List[Dict[str, object]], lic: LicenseInfo, *, only_if_unknown: bool = True) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for r in snippets:
        rr = dict(r)
        cur = (rr.get("license") or "").strip().upper()
        if (not only_if_unknown) or (cur in ("", "UNKNOWN")):
            rr["license"] = lic.spdx_id
            rr["license_url"] = lic.url
            rr["restricted"] = bool(lic.restricted)
        else:
            # Still set restricted if known GPLish
            rr["restricted"] = rr.get("restricted", _is_restricted(str(rr.get("license", ""))))
        out.append(rr)
    return out

