from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from krpc_snippets.index.keyword import KeywordIndex, search as kw_search


@dataclass
class VecStore:
    vectors: Dict[str, List[float]]
    dim: int
    model: str


def load_keyword_index(path: Path) -> KeywordIndex:
    return KeywordIndex.load(path)


def load_embeddings_jsonl(path: Path) -> VecStore:
    vectors: Dict[str, List[float]] = {}
    dim = 0
    model = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        vid = obj.get("id")
        vec = obj.get("vector")
        if vid and isinstance(vec, list):
            vectors[vid] = vec
            dim = dim or len(vec)
            model = model or (obj.get("model") or "")
    return VecStore(vectors=vectors, dim=dim, model=model)


def load_embeddings_sqlite(path: Path) -> VecStore:
    import sqlite3
    conn = sqlite3.connect(str(path))
    vectors: Dict[str, List[float]] = {}
    dim = 0
    model = ""
    for rid, mdl, d, vjson in conn.execute("select id, model, dim, vector from embeddings"):
        try:
            vec = json.loads(vjson)
        except Exception:
            continue
        vectors[rid] = vec
        dim = dim or int(d)
        model = model or (mdl or "")
    conn.close()
    return VecStore(vectors=vectors, dim=dim, model=model)


def load_embeddings_parquet(path: Path) -> VecStore:
    import pyarrow.parquet as pq  # type: ignore
    table = pq.read_table(path)
    vectors: Dict[str, List[float]] = {}
    dim = 0
    model = ""
    for row in table.to_pylist():
        rid = row.get("id")
        vec = row.get("vector")
        if rid and isinstance(vec, list):
            vectors[rid] = vec
            dim = dim or len(vec)
            model = model or (row.get("model") or "")
    return VecStore(vectors=vectors, dim=dim, model=model)


def _openai_client_or_none():
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        return None


def embed_query(text: str, *, model: str, dim: int, mock: bool, cache_dir: Optional[Path] = None) -> List[float]:
    if mock:
        rnd = random.Random(hash(text + model) & 0xFFFFFFFF)
        v = [rnd.uniform(-1.0, 1.0) for _ in range(max(1, dim))]
    else:
        client = _openai_client_or_none()
        if client is None:
            # Fallback to mock if no key available
            rnd = random.Random(hash(text + model) & 0xFFFFFFFF)
            v = [rnd.uniform(-1.0, 1.0) for _ in range(max(1, dim))]
        else:
            try:
                resp = client.embeddings.create(model=model, input=[text])
                v = list(resp.data[0].embedding)
            except Exception:
                rnd = random.Random(hash(text + model) & 0xFFFFFFFF)
                v = [rnd.uniform(-1.0, 1.0) for _ in range(max(1, dim))]
    # L2 normalize
    s = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / s for x in v]


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def vector_search(store: VecStore, qvec: List[float], k: int = 10) -> List[Tuple[str, float]]:
    scores: List[Tuple[str, float]] = []
    for rid, vec in store.vectors.items():
        sc = _cosine(vec, qvec)
        scores.append((rid, sc))
    scores.sort(key=lambda kv: -kv[1])
    return scores[:k]


def _minmax_norm(pairs: List[Tuple[str, float]]) -> Dict[str, float]:
    if not pairs:
        return {}
    vals = [sc for _, sc in pairs]
    mn = min(vals)
    mx = max(vals)
    if mx - mn <= 1e-12:
        return {rid: 1.0 for rid, _ in pairs}
    return {rid: (sc - mn) / (mx - mn) for rid, sc in pairs}


def search_hybrid(
    idx: KeywordIndex,
    store: VecStore,
    query: str,
    *,
    k: int = 10,
    alpha_keyword: float = 0.5,
    alpha_vector: float = 0.5,
    use_and: bool = False,
    category: Optional[str] = None,
    exclude_restricted: bool = False,
    mock_query_embed: bool = False,
    embed_model: Optional[str] = None,
) -> List[Dict]:
    # Keyword phase
    kw = kw_search(idx, query, k=k * 3, use_and=use_and, category=category, exclude_restricted=exclude_restricted)
    kw_norm = _minmax_norm([(rid, sc) for rid, sc, _ in kw])

    # Vector phase
    qvec = embed_query(query, model=(embed_model or store.model or "text-embedding-3-small"), dim=max(1, store.dim), mock=mock_query_embed)
    vec = vector_search(store, qvec, k=k * 3)
    vec_norm = _minmax_norm(vec)

    # Combine ids
    ids = set(list(kw_norm.keys()) + list(vec_norm.keys()))
    # Apply filters to ids not present in kw results
    def doc_ok(doc: Dict) -> bool:
        if exclude_restricted and doc.get("restricted"):
            return False
        if category and (category not in (doc.get("categories") or [])):
            return False
        return True

    for rid in list(ids):
        if rid not in idx.docs or not doc_ok(idx.docs[rid]):
            ids.discard(rid)

    fused: List[Tuple[str, float]] = []
    for rid in ids:
        f = alpha_keyword * kw_norm.get(rid, 0.0) + alpha_vector * vec_norm.get(rid, 0.0)
        fused.append((rid, f))
    fused.sort(key=lambda kv: -kv[1])

    out: List[Dict] = []
    for rid, sc in fused[:k]:
        doc = idx.docs.get(rid) or {}
        out.append({
            "id": rid,
            "score": sc,
            "kw_score": kw_norm.get(rid, 0.0),
            "vec_score": vec_norm.get(rid, 0.0),
            "name": doc.get("name"),
            "path": doc.get("path"),
            "categories": doc.get("categories"),
            "preview": (doc.get("description") or doc.get("name") or "")[:200],
        })
    return out

