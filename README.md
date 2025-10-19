KRPC Python Docs Scraper + MCP Server

Overview
- Scrape the kRPC documentation hosted at https://krpc.github.io/krpc/.
- Prefer Sphinx `objects.inv` for discovery, fall back to BFS from `python.html`.
- Extract clean text, headings, and anchors per page into JSONL.
- Filter to Python-only plus key overview pages (Welcome, Getting Started, Tutorials).
- Provide a local search index and an MCP server exposing search and retrieval tools.

Requirements
- Python 3.10+
- uv (Python package manager) installed and on PATH
  - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex`

Project layout
- Scraper: `scripts/scrape_krpc_docs.py`
- Filter: `scripts/filter_python_only.py`
- Dataset: `data/krpc_python_docs.jsonl` (+ `manifest.json`)
- Search lib: `krpc_index/`
- MCP server: `mcp_server/` (tools in `mcp_server/tools.py`)

Quick start
1) Scrape the docs to JSONL
- uv --directory krpc-docs run --with scrape scripts/scrape_krpc_docs.py
- Options:
  - `--start` seed URL (default: https://krpc.github.io/krpc/python.html)
  - `--base` docs base (default: https://krpc.github.io/krpc/)
  - `--out` output JSONL (default: data/krpc_python_docs.jsonl)
  - `--no-inventory` to force BFS crawl

2) Filter to Python + overview pages
- From a full crawl backup (created automatically on first filter):
  - uv --directory krpc-docs run --with scrape scripts/filter_python_only.py \
      --infile data/krpc_python_docs.full.jsonl \
      --outfile data/krpc_python_docs.jsonl
- This keeps URLs containing `/python`, the site root `/`, Getting Started, and Tutorials.

3) Try local search (optional sanity check)
- uv --directory krpc-docs run scripts/search_krpc_index.py "autopilot" --k 5
- uv --directory krpc-docs run scripts/search_krpc_index.py "getting started" --k 5

Run the MCP server (uv)
- As a module (recommended):
  - uv --directory krpc-docs run -m mcp_server.main
- Or via console script:
  - uv --directory krpc-docs run krpc-mcp

Using with Codex CLI
- Add the server (stdio transport) so Codex can launch it as needed:
  - codex mcp add krpc_docs -- uv --directory "$HOME/krpc-docs" run -m mcp_server.main
  - or use the console script: codex mcp add krpc_docs -- uv --directory "$HOME/krpc-docs" run krpc-mcp
- In chat, call tools:
  - search_krpc_docs: `Use krpc_docs to search_krpc_docs for 'autopilot'`
  - get_krpc_doc: `Use krpc_docs to get_krpc_doc with url 'https://krpc.github.io/krpc/python/client.html'`

Notes on environments
- uv automatically resolves and caches dependencies declared in `pyproject.toml`.
- You can create a dedicated venv explicitly if you prefer:
  - cd krpc-docs
  - uv venv --python 3.10
  - source .venv/bin/activate  # Windows: .venv\Scripts\activate
  - uv pip install -e .
  - python -m mcp_server.main

Output format (JSONL)
Each line is a page object:
{
  "url": "https://.../page.html",
  "title": "Page Title",
  "headings": ["Section 1", "Section 2"],
  "anchors": ["section-1", "section-2"],
  "content_text": "Cleaned text..."
}
