from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class RerankConfig:
    model: str = "gpt-4o-mini"
    top_m: int = 20
    beta_rerank: float = 0.7
    temperature: float = 0.2
    max_output_tokens: int = 400
    cache_dir: Path = Path("krpc-snippets/data/rerank_cache")
    mock: bool = False


def _ensure_cache(cfg: RerankConfig) -> None:
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)


def prepare_candidates(query: str, hybrid_results: List[Dict], top_m: int) -> List[Dict]:
    # Trim to Top-M with minimal fields
    items: List[Dict] = []
    for row in hybrid_results[: max(1, top_m)]:
        items.append({
            "id": row.get("id"),
            "name": row.get("name"),
            "categories": row.get("categories") or [],
            "description": (row.get("preview") or row.get("name") or "")[:200],
        })
    return items


def _build_messages(query: str, candidates: List[Dict]) -> List[Dict[str, str]]:
    sys_prompt = (
        "You are a strict JSON-only reranker. Given a query and candidates, return a JSON object with"
        " an 'items' array of {id, score} where score is a float 0..1 measuring relevance to the query."
        " Do not include explanations or extra fields."
    )
    user = json.dumps({
        "query": query,
        "candidates": candidates,
        "instructions": "Score each candidate id with a 0..1 float. Return: {\"items\": [{\"id\":..., \"score\":...}, ...]}"
    }, ensure_ascii=False)
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user},
    ]


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


def _cache_key(cfg: RerankConfig, query: str, candidates: List[Dict]) -> Path:
    blob = json.dumps({"m": cfg.model, "q": query, "ids": [c.get("id") for c in candidates]}, sort_keys=True)
    h = sha256(blob.encode("utf-8")).hexdigest()
    _ensure_cache(cfg)
    return cfg.cache_dir / f"{h}.json"


def call_openai_rerank(cfg: RerankConfig, query: str, candidates: List[Dict]) -> Dict[str, float]:
    cache_path = _cache_key(cfg, query, candidates)
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    client = _openai_client_or_none()
    if client is None:
        return mock_rerank(query, candidates)
    try:
        resp = client.chat.completions.create(
            model=cfg.model,
            temperature=cfg.temperature,
            response_format={"type": "json_object"},
            max_tokens=cfg.max_output_tokens,
            messages=_build_messages(query, candidates),
        )
        txt = resp.choices[0].message.content or "{}"
        obj = json.loads(txt)
        out: Dict[str, float] = {}
        for it in obj.get("items", []) or []:
            rid = str(it.get("id"))
            sc = float(it.get("score", 0.0))
            # clamp
            if sc < 0.0:
                sc = 0.0
            if sc > 1.0:
                sc = 1.0
            out[rid] = sc
        # Cache
        try:
            cache_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
        return out
    except Exception:
        return mock_rerank(query, candidates)


def _tokenize(s: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+", s.lower())


def mock_rerank(query: str, candidates: List[Dict]) -> Dict[str, float]:
    qt = set(_tokenize(query))
    out: Dict[str, float] = {}
    for c in candidates:
        text = " ".join([
            c.get("name") or "",
            c.get("description") or "",
            " ".join([str(x) for x in (c.get("categories") or [])])
        ]).lower()
        toks = set(_tokenize(text))
        overlap = len(qt & toks)
        sc = 0.0 if not qt else min(1.0, overlap / max(1.0, len(qt)))
        out[str(c.get("id"))] = sc
    return out


def rerank_results(query: str, hybrid_results: List[Dict], cfg: RerankConfig) -> List[Dict]:
    cand = prepare_candidates(query, hybrid_results, cfg.top_m)
    scores = mock_rerank(query, cand) if cfg.mock else call_openai_rerank(cfg, query, cand)
    out: List[Dict] = []
    for row in hybrid_results:
        rid = str(row.get("id"))
        rr = float(scores.get(rid, 0.0))
        fused_final = cfg.beta_rerank * rr + (1.0 - cfg.beta_rerank) * float(row.get("score", 0.0))
        r2 = dict(row)
        r2["rerank_score"] = rr
        r2["final_score"] = fused_final
        out.append(r2)
    out.sort(key=lambda r: (-r.get("final_score", 0.0), -r.get("score", 0.0), r.get("name") or ""))
    return out

