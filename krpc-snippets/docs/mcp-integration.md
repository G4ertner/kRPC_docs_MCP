# MCP Integration

Overview
- The main MCP server registers snippet tools directly (FastMCP).
- Tools are available alongside kRPC docs tools.

Tools
- `snippets_search(query, k=10, mode='keyword'|'hybrid', and_logic=False, category=None, exclude_restricted=False, rerank=False)`
- `snippets_get(id, include_code=False)`
- `snippets_resolve(id=None, name=None, max_bytes=25000, max_nodes=25)`
- `snippets_search_and_resolve(query, ...)` (convenience; returns Top‑1 bundle)

Usage (Codex CLI)
- Call the tools from the LLM: e.g., `snippets_search({"query":"NavHelper","k":5,"mode":"hybrid","rerank":true})`
- Inspect usage resource: `resource://snippets/usage`

Data paths (defaults)
- Snippets JSONL: `krpc-snippets/data/snippets_enriched.jsonl` (fallback: `snippets_extracted.jsonl`)
- Keyword index: `krpc-snippets/data/keyword_index.json`
- Embeddings: `krpc-snippets/data/embeddings.(sqlite|jsonl|parquet)`

OpenAI integration
- Hybrid search and rerank will use OpenAI when `OPENAI_API_KEY` is set; otherwise they fall back to mock behavior.

Import path note
- The MCP server shim adds `krpc-snippets` to `sys.path` so the side‑project package is importable without an editable install.

