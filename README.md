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

Connect to kRPC (game) — settings and code
- In KSP (other PC), open the kRPC window → Edit:
  - Protocol: Protobuf over TCP (for Python client)
  - Address: the PC’s LAN IP (not localhost) or set Manual and enter it
  - RPC port: leave default (commonly 50000) or set a free TCP port
  - Stream port: leave default (commonly 50001) or set a free TCP port
  - Advanced → Auto-accept new clients: optional ON (avoids confirmation prompts)
  - Ensure the OS firewall allows inbound TCP on both ports
- From this machine, Python example:
  ```py
  import krpc
  conn = krpc.connect(name='My Program', address='192.168.1.10', rpc_port=50000, stream_port=50001)
  print(conn.krpc.get_status().version)
  ```
- Helper function (provided): `mcp_server/krpc/client.py:connect_to_game(address, rpc_port=50000, stream_port=50001, name=None, timeout=5.0)`
  - Lazy-imports `krpc` and raises a helpful `KRPCConnectionError` on failures

Run the MCP server (uv)
- As a module (recommended):
  - uv --directory krpc-docs run -m mcp_server.main
- Or via console script:
  - uv --directory krpc-docs run krpc-mcp

Using with Codex CLI
- Add the server (stdio transport) so Codex can launch it as needed:
  - codex mcp add krpc_docs -- uv --directory "$HOME/krpc-docs" run -m mcp_server.main
  - or use the console script: codex mcp add krpc_docs -- uv --directory "$HOME/krpc-docs" run krpc-mcp
  - To enable kRPC tools automatically, include extras: `--with krpc`:
    - codex mcp remove krpc_docs
    - codex mcp add krpc_docs -- uv --with krpc --directory "$HOME/krpc-docs" run -m mcp_server.main

KSP Wiki tools (English)
- The server also exposes live KSP Wiki tools powered by the MediaWiki API:
  - search_ksp_wiki(query: str, limit: int = 10)
  - get_ksp_wiki_page(title: str, max_chars: int = 5000)
  - get_ksp_wiki_section(title: str, heading: str, max_chars: int = 3000)
- Examples in chat:
  - Use krpc_docs to search_ksp_wiki for 'delta-v'
  - Use krpc_docs to get_ksp_wiki_page with title 'Delta-v'
- Local CLI for quick checks (network required):
  - uv --directory krpc-docs run scripts/ksp_wiki_cli.py search "delta-v"
  - uv --directory krpc-docs run scripts/ksp_wiki_cli.py get "Delta-v"
  - uv --directory krpc-docs run scripts/ksp_wiki_cli.py section "Maneuver node" "Usage"
- In chat, call tools:
  - search_krpc_docs: `Use krpc_docs to search_krpc_docs for 'autopilot'`
  - get_krpc_doc: `Use krpc_docs to get_krpc_doc with url 'https://krpc.github.io/krpc/python/client.html'`

Script execution pipeline (execute_script)
- Tool: `krpc_docs.execute_script`
- Purpose: Run short, deterministic Python scripts against the live game with the kRPC connection auto-injected. The pipeline captures everything printed/logged and returns it to the agent, along with a parsed summary and error info.

Injected globals in your script
- `conn`: kRPC connection
- `vessel`: active vessel or `None` (guard for scenes without a vessel)
- `time`, `math`: standard modules
- `sleep(s)`, `deadline`, `check_time()`: timeout helpers; call `check_time()` inside loops
- `logging`, `log(msg)`: logging is preconfigured and captured

Contract and best practices
- Do not import kRPC or connect manually. The runner handles it.
- Use `print()` and/or the `logging` module; both appear in the transcript.
- Use bounded loops and call `check_time()`; the runner enforces a hard wall-time timeout.
- End with a `SUMMARY:` block (single-line or multi-line starting with `SUMMARY:`) so the agent can quickly understand outcomes.
- `pause_on_end` is best-effort. It may be unavailable depending on client/server versions.

Call from CLI (local sanity check)
- Hello/log/summary example:
  - `uv run scripts/krpc_execute_script_cli.py --address 192.168.2.28 --code "print('hello'); logging.info('note'); print('SUMMARY: ok')"`
  - Returns JSON: `{ ok, summary, transcript, stdout, stderr, error, paused, timing, code_stats }`

Call from MCP (in chat)
- `Use krpc_docs to execute_script with code "print('hello'); print('SUMMARY: done')" and address '192.168.2.28'`

Example script (gravity turn step)
```
# (No imports or kRPC connect – runner injects conn, vessel, logging, etc.)
logging.info("Starting gravity turn ascent step")

if vessel is None:
    print("SUMMARY: aborted — no active vessel in scene")
else:
    flight = vessel.flight()
    logging.info(f"STATE: Ap={vessel.orbit.apoapsis_altitude:.0f} m")

    vessel.control.throttle = 1.0
    logging.info("Throttle set to 100%")

    t0 = conn.space_center.ut
    while flight.mean_altitude < 10000 and conn.space_center.ut - t0 < 120:
        check_time()
        alt = flight.mean_altitude
        vs = flight.vertical_speed
        logging.info(f"STATE: alt={alt:.0f} vs={vs:.1f}")
        if alt > 3000: vessel.control.pitch = 80
        if alt > 7000: vessel.control.pitch = 60
        sleep(0.5)

    print("""SUMMARY:
phase: initial gravity turn
achieved: yes
altitude_m: {:.1f}
next_step: begin horizontal acceleration to build orbital velocity
""".format(flight.mean_altitude))
```

Return fields
- `ok`: True/False
- `summary`: Parsed from the stdout portion beginning with `SUMMARY:` (if present)
- `transcript`: Combined stdout + stderr so exceptions are visible alongside prints/logs
- `stdout`, `stderr`: Raw channels
- `error`: Parsed exception info (type/message/line) when available
- `paused`: True/False/None (best-effort)
- `timing.exec_time_s`: Wall time in seconds
- `code_stats`: `{ line_count, has_imports }`

Notes on environments
- uv automatically resolves and caches dependencies declared in `pyproject.toml`.
- kRPC tools are optional. Install support with extras when needed:
  - uv --directory krpc-docs run --with krpc -m mcp_server.main
  - or: uv pip install -e ".[krpc]"
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

Vessel blueprint tools
- Tools:
  - `get_vessel_blueprint(address, ...)` → JSON blueprint (meta, stages, engines, parts)
  - `get_part_tree(address, ...)` → JSON parts[] with parent/children, stage, modules, resources
  - `get_blueprint_ascii(address, ...)` → Human-readable per-stage summary
- Resource cache: `resource://blueprints/latest` (call `get_vessel_blueprint` first)
- Export diagrams:
  - `export_blueprint_diagram(address, format='svg'|'png'|'both', out_dir=?)` → saves to `artifacts/blueprints/` by default
  - Resources after export:
    - `resource://blueprints/last-diagram.svg` — SVG (text)
    - `resource://blueprints/last-diagram.png` — JSON with base64 PNG payload ({mime, data_base64})
- CLI sanity check:
  - `uv run scripts/krpc_blueprint_cli.py --address 192.168.2.28`
  - or use MCP: `Use krpc_docs to get_vessel_blueprint with address '192.168.2.28'`, then fetch `resource://blueprints/latest`

Blueprint usage playbook
- Resource: `resource://playbooks/vessel-blueprint-usage`
- Describes how agents should read blueprint fields and plan safe staging/burns.

Export quick test
- SVG only:
  - `Use krpc_docs to export_blueprint_diagram with address '192.168.2.28' and format 'svg'`
  - Then fetch `resource://blueprints/last-diagram.svg`
  - Or open the saved file in `artifacts/blueprints/`.
- PNG (requires Pillow):
  - `uv pip install pillow`
  - `Use krpc_docs to export_blueprint_diagram with address '192.168.2.28' and format 'png'`
  - Then fetch `resource://blueprints/last-diagram.png` (base64 JSON), or open the saved PNG path from the tool output.
