from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class Snippet:
    id: str
    repo: str
    commit: str
    path: str
    lang: str
    name: str
    description: str
    code: str
    categories: List[str]
    dependencies: List[str]
    license: str
    license_url: str
    created_at: str

    restricted: Optional[bool] = None
    inputs: Optional[List[str]] = None
    outputs: Optional[List[str]] = None
    when_to_use: Optional[str] = None
    size_bytes: Optional[int] = None
    lines_of_code: Optional[int] = None


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def calc_size_bytes(code: str) -> int:
    return len(code.encode("utf-8"))


def calc_loc(code: str) -> int:
    return code.count("\n") + (1 if code and not code.endswith("\n") else 0)


def asdict(sn: Snippet) -> Dict[str, Any]:
    from dataclasses import asdict as _asdict

    return _asdict(sn)

