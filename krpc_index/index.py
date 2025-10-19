from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass
class Doc:
    url: str
    title: str
    headings: List[str]
    anchors: List[str]
    content_text: str


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _sentences(text: str) -> List[str]:
    # Simple sentence segmentation: split on ., !, ?, or newlines
    parts = re.split(r"(?<=[\.!?])\s+|\n+", text)
    # Keep non-empty
    return [p.strip() for p in parts if p and p.strip()]


def load_dataset(path: Path) -> List[Doc]:
    docs: List[Doc] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            docs.append(
                Doc(
                    url=obj.get("url", ""),
                    title=obj.get("title", ""),
                    headings=obj.get("headings", []) or [],
                    anchors=obj.get("anchors", []) or [],
                    content_text=obj.get("content_text", ""),
                )
            )
    return docs


class KRPCSearchIndex:
    def __init__(self, docs: Iterable[Doc]):
        self.docs: List[Doc] = list(docs)
        self.by_url: Dict[str, Doc] = {d.url: d for d in self.docs}
        # Inverted index: token -> {doc_idx: tf}
        self.inv: Dict[str, Dict[int, int]] = {}
        # For boosts
        self.title_tokens: Dict[int, set[str]] = {}
        self.heading_tokens: Dict[int, set[str]] = {}

        for i, d in enumerate(self.docs):
            # Title/headings token sets (for boosts)
            t_tokens = set(_tokenize(d.title))
            h_tokens = set()
            for h in d.headings:
                h_tokens.update(_tokenize(h))
            self.title_tokens[i] = t_tokens
            self.heading_tokens[i] = h_tokens

            # Full-text bag of words from title + headings + body
            all_text = "\n".join([d.title, *d.headings, d.content_text])
            for tok in _tokenize(all_text):
                bucket = self.inv.setdefault(tok, {})
                bucket[i] = bucket.get(i, 0) + 1

    def get(self, url: str) -> Doc | None:
        return self.by_url.get(url)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Doc, float, str]]:
        q_tokens = [t for t in _tokenize(query) if t]
        if not q_tokens:
            return []

        scores: Dict[int, float] = {}
        for tok in q_tokens:
            postings = self.inv.get(tok)
            if not postings:
                continue
            for doc_idx, tf in postings.items():
                # Base content weight by term frequency
                score = tf * 1.0
                # Boost if token appears in title/headings
                if tok in self.title_tokens.get(doc_idx, ()):  # +2 each hit
                    score += 2.0
                if tok in self.heading_tokens.get(doc_idx, ()):  # +1 each hit
                    score += 1.0
                scores[doc_idx] = scores.get(doc_idx, 0.0) + score

        # Sort by score desc, then shorter title (tie-breaker), then URL
        ranked = sorted(
            scores.items(), key=lambda kv: (-kv[1], len(self.docs[kv[0]].title), self.docs[kv[0]].url)
        )[:top_k]

        results: List[Tuple[Doc, float, str]] = []
        for idx, sc in ranked:
            d = self.docs[idx]
            snippet = self._make_snippet(d, q_tokens)
            results.append((d, sc, snippet))
        return results

    def _make_snippet(self, d: Doc, q_tokens: List[str], max_len: int = 180) -> str:
        hay = d.content_text or d.title
        # Find first sentence containing any token
        sent = None
        for s in _sentences(hay):
            s_l = s.lower()
            if any(t in s_l for t in q_tokens):
                sent = s
                break
        if sent is None:
            sent = hay.strip().split("\n", 1)[0]
        if len(sent) <= max_len:
            return sent
        return sent[: max_len - 1].rstrip() + "…"

