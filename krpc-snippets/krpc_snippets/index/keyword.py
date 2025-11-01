from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _split_camel(token: str) -> List[str]:
    # Split CamelCase and snake_case tokens into lowercase pieces
    # Example: NavHelper -> [nav, helper]
    parts: List[str] = []
    buf = ""
    for ch in token:
        if ch.isupper() and buf and not buf[-1].isupper():
            parts.append(buf)
            buf = ch.lower()
        else:
            buf += ch.lower()
    if buf:
        parts.append(buf)
    # Split underscores inside
    out: List[str] = []
    for p in parts:
        out.extend([s for s in p.split("_") if s])
    return out


def _tokenize(text: str) -> List[str]:
    toks: List[str] = []
    for m in _TOKEN_RE.findall(text or ""):
        if not m:
            continue
        for s in _split_camel(m):
            if s:
                toks.append(s)
    return toks


@dataclass
class KeywordConfig:
    weight_name: float = 3.0
    weight_categories: float = 2.0
    weight_inputs: float = 1.5
    weight_description: float = 1.0
    weight_code_head: float = 0.5
    code_head_chars: int = 300
    stopwords: List[str] = field(default_factory=lambda: [
        "the", "and", "or", "to", "of", "a", "in", "on", "for", "with", "by",
    ])


@dataclass
class KeywordIndex:
    vocab: Dict[str, Dict[str, float]]
    df: Dict[str, int]
    docs: Dict[str, Dict]
    N: int
    cfg: KeywordConfig

    def save(self, path: Path) -> None:
        data = {
            "vocab": self.vocab,
            "df": self.df,
            "docs": self.docs,
            "N": self.N,
            "cfg": self.cfg.__dict__,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "KeywordIndex":
        obj = json.loads(path.read_text(encoding="utf-8"))
        cfg = KeywordConfig(**obj.get("cfg", {}))
        return KeywordIndex(vocab=obj["vocab"], df=obj["df"], docs=obj["docs"], N=int(obj["N"]), cfg=cfg)


def _add_tokens(weighted_tf: Dict[str, float], text: str, weight: float, stopwords: List[str]) -> None:
    for t in _tokenize(text):
        if t in stopwords:
            continue
        weighted_tf[t] = weighted_tf.get(t, 0.0) + weight


def build_index(snippets: List[Dict], cfg: Optional[KeywordConfig] = None) -> KeywordIndex:
    cfg = cfg or KeywordConfig()
    vocab: Dict[str, Dict[str, float]] = {}
    df: Dict[str, int] = {}
    docs: Dict[str, Dict] = {}

    for rec in snippets:
        rid = rec.get("id")
        if not rid:
            continue
        wtf: Dict[str, float] = {}
        # name
        if rec.get("name"):
            _add_tokens(wtf, rec["name"], cfg.weight_name, cfg.stopwords)
        # categories
        for c in (rec.get("categories") or []):
            _add_tokens(wtf, str(c), cfg.weight_categories, cfg.stopwords)
        # inputs
        for inp in (rec.get("inputs") or []):
            _add_tokens(wtf, str(inp), cfg.weight_inputs, cfg.stopwords)
        # description
        if rec.get("description"):
            _add_tokens(wtf, rec["description"], cfg.weight_description, cfg.stopwords)
        # code head
        if rec.get("code"):
            _add_tokens(wtf, rec["code"][: cfg.code_head_chars], cfg.weight_code_head, cfg.stopwords)

        # Update vocab/df
        for tok, tfw in wtf.items():
            bucket = vocab.setdefault(tok, {})
            if rid not in bucket:
                df[tok] = df.get(tok, 0) + 1
            bucket[rid] = bucket.get(rid, 0.0) + tfw

        # Store doc meta
        docs[rid] = {
            "name": rec.get("name"),
            "path": rec.get("path"),
            "categories": rec.get("categories") or [],
            "restricted": bool(rec.get("restricted")) if rec.get("restricted") is not None else False,
            "description": rec.get("description") or "",
        }

    return KeywordIndex(vocab=vocab, df=df, docs=docs, N=len(docs), cfg=cfg)


def _idf(N: int, df: int) -> float:
    return math.log(1.0 + (N / (1.0 + df)))


def _preview(doc: Dict, query_tokens: List[str], code_head: Optional[str] = None) -> str:
    # Prefer description; fallback to name
    text = doc.get("description") or doc.get("name") or ""
    t = text.strip()
    if not t:
        t = (code_head or "").strip()[:120]
    # Simple preview without heavy highlighting (CLI will print context)
    return t[:200]


def search(
    index: KeywordIndex,
    query: str,
    *,
    k: int = 10,
    use_and: bool = False,
    category: Optional[str] = None,
    exclude_restricted: bool = False,
) -> List[Tuple[str, float, Dict]]:
    q_tokens = [t for t in _tokenize(query) if t and t not in index.cfg.stopwords]
    if not q_tokens:
        return []
    # Candidate doc ids (OR/AND)
    candidate_ids: Optional[set] = None
    for t in q_tokens:
        ids = set(index.vocab.get(t, {}).keys())
        if candidate_ids is None:
            candidate_ids = ids
        else:
            candidate_ids = (candidate_ids & ids) if use_and else (candidate_ids | ids)
    if not candidate_ids:
        return []
    # Filters
    def doc_ok(doc: Dict) -> bool:
        if exclude_restricted and doc.get("restricted"):
            return False
        if category and (category not in (doc.get("categories") or [])):
            return False
        return True

    # Score
    scores: Dict[str, float] = {}
    for t in q_tokens:
        postings = index.vocab.get(t)
        if not postings:
            continue
        idf = _idf(index.N, index.df.get(t, 0))
        for rid, tfw in postings.items():
            if rid not in candidate_ids:
                continue
            doc = index.docs.get(rid) or {}
            if not doc_ok(doc):
                continue
            scores[rid] = scores.get(rid, 0.0) + (tfw * idf)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], index.docs.get(kv[0], {}).get("name", "")))[:k]
    results: List[Tuple[str, float, Dict]] = []
    for rid, sc in ranked:
        doc = index.docs.get(rid) or {}
        results.append((rid, sc, doc))
    return results

