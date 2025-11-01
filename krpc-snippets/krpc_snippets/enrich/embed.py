from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class EmbedConfig:
    model: str = "text-embedding-3-small"
    fields: List[str] = field(default_factory=lambda: ["name", "description", "code_head"])  # order matters
    code_head_chars: int = 800
    normalize: bool = True
    batch_size: int = 64
    cache_dir: Path = Path("krpc-snippets/data/embed_cache")
    mock: bool = False


EMBED_VERSION = "v1"


def _ensure_cache_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_key(rec: Dict, cfg: EmbedConfig) -> str:
    # Version + model + fields + truncated text length
    rid = rec.get("id") or "noid"
    key_parts = [EMBED_VERSION, cfg.model, ",".join(cfg.fields), str(cfg.code_head_chars), rid]
    return "__" + "_".join(part.replace("/", "_") for part in key_parts)


def _cache_path(cfg: EmbedConfig, rec: Dict) -> Path:
    name = _cache_key(rec, cfg) + ".json"
    return _ensure_cache_dir(cfg.cache_dir) / name


def build_input_text(rec: Dict, cfg: EmbedConfig) -> str:
    parts: List[str] = []
    for f in cfg.fields:
        if f == "name" and rec.get("name"):
            parts.append(f"name: {rec['name']}")
        elif f == "description" and rec.get("description"):
            parts.append(f"description: {rec['description']}")
        elif f == "code_head" and rec.get("code"):
            code = rec["code"][: max(0, int(cfg.code_head_chars))]
            parts.append(f"code: {code}")
        elif rec.get(f) is not None:
            parts.append(f"{f}: {rec.get(f)}")
    return "\n".join(parts)


def _openai_client_or_none():
    try:
        import openai  # type: ignore
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    except Exception:
        return None


def _embed_openai(client, model: str, texts: List[str]) -> Tuple[List[List[float]], int]:
    # Returns (vectors, dimension)
    resp = client.embeddings.create(model=model, input=texts)
    vecs = [item.embedding for item in resp.data]
    dim = len(vecs[0]) if vecs else 0
    return vecs, dim


def _embed_mock(ids: List[str], dim: int = 64) -> Tuple[List[List[float]], int]:
    vecs: List[List[float]] = []
    for rid in ids:
        rnd = random.Random(hash(rid) & 0xFFFFFFFF)
        v = [rnd.uniform(-1.0, 1.0) for _ in range(dim)]
        vecs.append(v)
    return vecs, dim


def _l2_normalize(v: List[float]) -> List[float]:
    s = math.sqrt(sum(x * x for x in v))
    if s <= 1e-12:
        return v
    return [x / s for x in v]


def embed_records(records: List[Dict], cfg: Optional[EmbedConfig] = None) -> List[Dict]:
    cfg = cfg or EmbedConfig()
    out: List[Dict] = []
    client = None if cfg.mock else _openai_client_or_none()

    batch_ids: List[str] = []
    batch_texts: List[str] = []
    batch_recs: List[Dict] = []

    def flush_batch():
        nonlocal out, batch_ids, batch_texts, batch_recs
        if not batch_texts:
            return
        try:
            if client is not None:
                vecs, dim = _embed_openai(client, cfg.model, batch_texts)
            else:
                vecs, dim = _embed_mock(batch_ids)
        except Exception:
            # Fallback to mock for this batch
            vecs, dim = _embed_mock(batch_ids)
        for rec, rid, vec in zip(batch_recs, batch_ids, vecs):
            vecn = _l2_normalize(vec) if cfg.normalize else vec
            emb = {"id": rec.get("id"), "model": cfg.model, "dim": dim, "vector": vecn}
            out.append(emb)
            # Cache
            try:
                _cache_path(cfg, rec).write_text(json.dumps(emb, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        batch_ids, batch_texts, batch_recs = [], [], []

    for rec in records:
        # Cache lookup
        cache_file = _cache_path(cfg, rec)
        if cache_file.exists():
            try:
                emb = json.loads(cache_file.read_text(encoding="utf-8"))
                out.append(emb)
                continue
            except Exception:
                pass
        text = build_input_text(rec, cfg)
        batch_ids.append(rec.get("id", ""))
        batch_texts.append(text)
        batch_recs.append(rec)
        if len(batch_texts) >= cfg.batch_size:
            flush_batch()
            time.sleep(0.05)  # gentle pacing
    flush_batch()
    return out


def write_sqlite(embeddings: List[Dict], path: Path) -> int:
    import sqlite3
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = [
        (
            e.get("id"),
            e.get("model"),
            int(e.get("dim", 0)),
            json.dumps(e.get("vector")),
            now,
        )
        for e in embeddings
    ]
    conn.executemany(
        """
        INSERT INTO embeddings (id, model, dim, vector, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          model=excluded.model,
          dim=excluded.dim,
          vector=excluded.vector,
          updated_at=excluded.updated_at
        """,
        rows,
    )
    conn.commit()
    n = len(rows)
    conn.close()
    return n


def write_jsonl(embeddings: List[Dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in embeddings:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(embeddings)


def write_parquet(embeddings: List[Dict], path: Path) -> int:
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        raise RuntimeError("pyarrow is required for Parquet output. Install with 'uv pip install pyarrow'.")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Convert to columns
    ids = [e.get("id") for e in embeddings]
    models = [e.get("model") for e in embeddings]
    dims = [int(e.get("dim", 0)) for e in embeddings]
    vecs = [e.get("vector") for e in embeddings]
    table = pa.table({
        "id": pa.array(ids, type=pa.string()),
        "model": pa.array(models, type=pa.string()),
        "dim": pa.array(dims, type=pa.int32()),
        "vector": pa.array(vecs, type=pa.list_(pa.float32())),
    })
    pq.write_table(table, path)
    return len(embeddings)

