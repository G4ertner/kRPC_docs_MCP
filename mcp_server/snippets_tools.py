from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from .server import mcp

# Ensure the side-project package 'krpc_snippets' is importable when running the MCP server
# The package lives under 'krpc-snippets/krpc_snippets', so we add 'krpc-snippets' to sys.path.
import sys as _sys
_SIDE_DIR = Path(__file__).resolve().parents[1] / "krpc-snippets"
if _SIDE_DIR.exists() and str(_SIDE_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SIDE_DIR))


# ---------- Paths & loaders ----------

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_paths() -> Dict[str, Path]:
    root = _repo_root()
    base = root / "krpc-snippets" / "data"
    return {
        "snippets_enriched": base / "snippets_enriched.jsonl",
        "snippets_extracted": base / "snippets_extracted.jsonl",
        "keyword_index": base / "keyword_index.json",
        "emb_sqlite": base / "embeddings.sqlite",
        "emb_jsonl": base / "embeddings.jsonl",
        "emb_parquet": base / "embeddings.parquet",
    }


def _snippets_path() -> Path:
    p = _default_paths()
    return p["snippets_enriched"] if p["snippets_enriched"].exists() else p["snippets_extracted"]


def _load_snippets(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = path or _snippets_path()
    recs: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s:
                continue
            recs.append(json.loads(s))
    except Exception:
        pass
    return recs


# ---------- Search helpers ----------

def _build_keyword_index(recs: List[Dict[str, Any]]):
    from krpc_snippets.index.keyword import build_index, KeywordConfig

    cfg = KeywordConfig()
    return build_index(recs, cfg)


def _load_keyword_index_or_build() -> Any:
    from krpc_snippets.index.keyword import KeywordIndex

    p = _default_paths()["keyword_index"]
    if p.exists():
        try:
            return KeywordIndex.load(p)
        except Exception:
            pass
    recs = _load_snippets()
    return _build_keyword_index(recs)


def _load_vec_store_or_none():
    from krpc_snippets.search.hybrid import load_embeddings_sqlite, load_embeddings_jsonl, load_embeddings_parquet

    p = _default_paths()
    try:
        if p["emb_sqlite"].exists():
            return load_embeddings_sqlite(p["emb_sqlite"])
        if p["emb_jsonl"].exists():
            return load_embeddings_jsonl(p["emb_jsonl"])
        if p["emb_parquet"].exists():
            return load_embeddings_parquet(p["emb_parquet"])
    except Exception:
        return None
    return None


def _keyword_search(idx, query: str, k: int, use_and: bool, category: Optional[str], exclude_restricted: bool) -> List[Dict[str, Any]]:
    from krpc_snippets.index.keyword import search as kw_search

    res = kw_search(idx, query, k=k, use_and=use_and, category=category, exclude_restricted=exclude_restricted)
    out: List[Dict[str, Any]] = []
    for rid, sc, doc in res:
        out.append({
            "id": rid,
            "name": doc.get("name"),
            "path": doc.get("path"),
            "categories": doc.get("categories"),
            "preview": (doc.get("description") or doc.get("name") or "")[:200],
            "scores": {"kw": sc},
        })
    return out


def _hybrid_search(query: str, k: int, use_and: bool, category: Optional[str], exclude_restricted: bool, rerank: bool) -> List[Dict[str, Any]]:
    from krpc_snippets.search.hybrid import load_keyword_index, search_hybrid
    from krpc_snippets.search.hybrid import load_embeddings_sqlite, load_embeddings_jsonl, load_embeddings_parquet
    from krpc_snippets.search.rerank import RerankConfig, rerank_results

    p = _default_paths()
    idx = load_keyword_index(p["keyword_index"]) if p["keyword_index"].exists() else _load_keyword_index_or_build()
    # Embeddings
    store = None
    if p["emb_sqlite"].exists():
        store = load_embeddings_sqlite(p["emb_sqlite"])
    elif p["emb_jsonl"].exists():
        store = load_embeddings_jsonl(p["emb_jsonl"])
    elif p["emb_parquet"].exists():
        store = load_embeddings_parquet(p["emb_parquet"])
    if store is None:
        # Fallback to keyword-only
        return _keyword_search(idx, query, k, use_and, category, exclude_restricted)

    mock_query = not bool(os.environ.get("OPENAI_API_KEY"))
    res = search_hybrid(
        idx,
        store,
        query,
        k=k,
        use_and=use_and,
        category=category,
        exclude_restricted=exclude_restricted,
        mock_query_embed=mock_query,
    )
    if rerank:
        cfg = RerankConfig(mock=not bool(os.environ.get("OPENAI_API_KEY")))
        res = rerank_results(query, res, cfg)
    # Shape output
    out: List[Dict[str, Any]] = []
    for row in res:
        out.append({
            "id": row.get("id"),
            "name": row.get("name"),
            "path": row.get("path"),
            "categories": row.get("categories"),
            "preview": row.get("preview"),
            "scores": {
                "fused": row.get("score"),
                "kw": row.get("kw_score"),
                "vec": row.get("vec_score"),
                "rerank": row.get("rerank_score"),
            },
        })
    return out


# ---------- FastMCP tools ----------


@mcp.tool()
def snippets_search(query: str, k: int = 10, mode: str = "keyword", and_logic: bool = False, category: str | None = None, exclude_restricted: bool = False, rerank: bool = False) -> str:
    """
    Search the snippet library.

    Args:
      query: free-text query
      k: number of results
      mode: 'keyword' or 'hybrid'
      and_logic: when true, use AND semantics for keyword token combination
      category: optional category filter
      exclude_restricted: exclude GPL/AGPL/LGPL when true
      rerank: re-score Top-M with an LLM (when available) in hybrid mode
    Returns:
      JSON: { items: [...], source: {...} }
    """
    idx = _load_keyword_index_or_build()
    if (mode or "keyword").lower() == "keyword":
        items = _keyword_search(idx, query, k, and_logic, category, exclude_restricted)
        src = {"mode": "keyword", "index": str(_default_paths()["keyword_index"]) }
    else:
        items = _hybrid_search(query, k, and_logic, category, exclude_restricted, rerank)
        src = {"mode": "hybrid", "index": str(_default_paths()["keyword_index"]) }
    return json.dumps({"items": items, "source": src})


@mcp.tool()
def snippets_get(id: str, include_code: bool = False) -> str:
    """
    Get a snippet record by id.
    Returns JSON: { ok, snippet? }.
    """
    recs = _load_snippets()
    for r in recs:
        if r.get("id") == id:
            out = dict(r)
            if not include_code:
                out["code"] = ("" if out.get("code") else out.get("code"))
            return json.dumps({"ok": True, "snippet": out})
    return json.dumps({"ok": False, "error": f"id not found: {id}"})


@mcp.tool()
def snippets_resolve(id: str | None = None, name: str | None = None, max_bytes: int = 25000, max_nodes: int = 25) -> str:
    """
    Resolve a snippet (by id or module.qualname) into a paste-ready bundle including dependencies.

    Returns JSON: { ok, bundle_code?, include_ids?, unresolved?, truncated?, stats? }.
    """
    from krpc_snippets.resolve.resolve_snippet import resolve_snippet as _resolve

    if not id and not name:
        return json.dumps({"ok": False, "error": "Provide id or name"})
    try:
        res = _resolve(
            target_id=id,
            target_name=name,
            snippets_path=_snippets_path(),
            size_cap_bytes=int(max_bytes),
            size_cap_nodes=int(max_nodes),
        )
        return json.dumps({
            "ok": True,
            "bundle_code": res.bundle_code,
            "include_ids": res.include_ids,
            "unresolved": res.unresolved_deps,
            "truncated": res.truncated,
            "stats": res.stats,
        })
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@mcp.tool()
def snippets_search_and_resolve(query: str, k: int = 10, mode: str = "hybrid", rerank: bool = False, and_logic: bool = False, category: str | None = None, exclude_restricted: bool = False, max_bytes: int = 25000, max_nodes: int = 25) -> str:
    """
    Search and resolve top-1 result into a code bundle.

    Returns JSON with top result metadata and bundle fields.
    """
    items = json.loads(snippets_search(query, k=k, mode=mode, and_logic=and_logic, category=category, exclude_restricted=exclude_restricted, rerank=rerank)).get("items", [])
    if not items:
        return json.dumps({"ok": False, "error": "No results"})
    top = items[0]
    rid = top.get("id")
    res = json.loads(snippets_resolve(id=rid, name=None, max_bytes=max_bytes, max_nodes=max_nodes))
    res["top"] = top
    return json.dumps(res)


# ---------- Resource ----------


_USAGE = (
    "Snippets Tools (krpc-snippets)\n\n"
    "snippets_search(query, k=10, mode='keyword'|'hybrid', and_logic=False, category=None, exclude_restricted=False, rerank=False)\n"
    "snippets_get(id, include_code=False)\n"
    "snippets_resolve(id=None, name=None, max_bytes=25000, max_nodes=25)\n"
    "snippets_search_and_resolve(query, ...) — convenience that returns top-1 bundle\n\n"
    "Data paths (relative to repo root):\n"
    "- Snippets JSONL: krpc-snippets/data/snippets_enriched.jsonl (fallback: snippets_extracted.jsonl)\n"
    "- Keyword index: krpc-snippets/data/keyword_index.json\n"
    "- Embeddings: krpc-snippets/data/embeddings.(sqlite|jsonl|parquet)\n\n"
    "Notes:\n- Hybrid/rerank use OpenAI when OPENAI_API_KEY is set; otherwise mock.\n"
)


@mcp.resource("resource://snippets/usage")
def get_snippets_usage() -> str:
    return _USAGE
