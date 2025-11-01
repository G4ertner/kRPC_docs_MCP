from __future__ import annotations

import math
from typing import Iterable, List, Dict, Any


def _extract_ids(results: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for r in results:
        if isinstance(r, str):
            out.append(r)
        elif isinstance(r, dict):
            rid = r.get("id")
            if rid:
                out.append(str(rid))
        elif isinstance(r, (tuple, list)) and r:
            out.append(str(r[0]))
    return out


def topk_accuracy(results: Iterable[Any], expected_ids: Iterable[str], k: int) -> float:
    ids = _extract_ids(results)[:k]
    exp = set(str(x) for x in expected_ids)
    return 1.0 if any(i in exp for i in ids) else 0.0


def mrr(results: Iterable[Any], expected_ids: Iterable[str]) -> float:
    ids = _extract_ids(results)
    exp = set(str(x) for x in expected_ids)
    for i, rid in enumerate(ids, start=1):
        if rid in exp:
            return 1.0 / i
    return 0.0


def ndcg_at_k(results: Iterable[Any], expected_ids: Iterable[str], k: int) -> float:
    ids = _extract_ids(results)[:k]
    exp = set(str(x) for x in expected_ids)
    dcg = 0.0
    for i, rid in enumerate(ids, start=1):
        rel = 1.0 if rid in exp else 0.0
        if rel > 0:
            dcg += (2 ** rel - 1) / math.log2(1 + i)
    # Ideal DCG: all relevant (binary) at top
    R = min(len(exp), k)
    idcg = sum((2 ** 1 - 1) / math.log2(1 + i) for i in range(1, R + 1))
    return (dcg / idcg) if idcg > 0 else 0.0

