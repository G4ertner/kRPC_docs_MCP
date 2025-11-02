# KSP Mission‑Control Protocol (MCP) Server

![Kerbal mission chaos](readme-banner.png)

## Introduction

The **KSP Mission‑Control Protocol (MCP) server** transforms Kerbal Space Program into a remote‑controlled playground for AI agents and human operators.  By combining [kRPC](https://krpc.github.io/krpc/) with a rich set of mission tools, it lets you:

- Execute short, deterministic Python scripts inside a live KSP instance, with the connection and vessel objects injected for you.
- Inspect your vessel’s blueprint, part tree, stages and engines, and export diagrams in SVG or PNG.
- Search and retrieve pages from the KSP Wiki or the official kRPC documentation on demand.
- Access playbooks and guides that teach agents how to read blueprints and plan safe staging and burns.

Under the hood, the server also scrapes and indexes the kRPC docs to provide a fast, local search backend.  Those pipelines are described in a later section; the focus here is on the mission‑control capabilities.

## Core capabilities

### 🛰️ Live script execution

Call the `execute_script` tool to run Python code against your running game.  The MCP server automatically injects useful globals:

- `conn`: your live kRPC connection
- `vessel`: the active vessel (or `None` if you’re not in flight)
- `time`, `math`, `sleep`, `deadline` and `check_time()` helpers
- a preconfigured `logging` module and a `log(msg)` convenience function

Scripts should not import `krpc` or open their own connections; they should print or log output and include a `SUMMARY:` at the end.  The tool returns a structured JSON result with `summary`, `transcript`, timing and error fields.  See the [example gravity‑turn script](#example-script-gravity-turn) below.

### 🛠️ Vessel blueprints & diagrams

Need to inspect your craft?  The blueprint tools expose:

- `get_vessel_blueprint`: returns a JSON blueprint with metadata, stages, engines and parts.
- `get_part_tree`: returns a hierarchical list of all parts with parent/child relationships, modules and resources.
- `get_blueprint_ascii`: produces a human‑readable per‑stage summary of the vessel.
- `export_blueprint_diagram`: generates a diagram (SVG or PNG) of your vessel’s staging and structure.  The output is cached for retrieval via `resource://` URIs.

These tools let agents understand the craft’s structure, plan staging and fuel usage, and generate diagrams for mission briefings.

### 📚 KSP Wiki & doc search

The MCP server wraps the MediaWiki API and the locally indexed kRPC documentation.  Tools include:

- `search_ksp_wiki(query, limit)`, `get_ksp_wiki_page(title, max_chars)` and `get_ksp_wiki_section(title, heading, max_chars)` for looking up game concepts (e.g. delta‑v, maneuver nodes, ISRU).  Perfect for agents that need domain knowledge.
- `search_krpc_docs(query, k)` and `get_krpc_doc(url, max_chars)` for searching and retrieving the kRPC Python API reference without leaving chat.

### 📖 Playbooks & guidance

The server ships with a **vessel blueprint usage playbook** (`resource://playbooks/vessel-blueprint-usage`) that explains how to read blueprint fields, plan safe staging, and design burn sequences.  Agents can fetch this resource to learn best practices when working with the blueprint data.

## Quick start

1. **Install dependencies**

   This project requires Python 3.10+ and [uv](https://github.com/astral-sh/uv) for running scripts and managing dependencies.  Optionally install the `krpc` extras to enable kRPC connectivity and `Pillow` if you want PNG diagram export.

   ```sh
   # Clone the repository
   git clone https://github.com/G4ertner/kRPC_docs_MCP.git
   cd kRPC_docs_MCP

   # Use uv to run the MCP server
   curl -LsSf https://astral.sh/uv/install.sh | sh  # install uv
   uv pip install -e .[krpc]  # install dependencies with krpc extras
   uv pip install pillow     # optional, for PNG diagram export
   ```

2. **Launch the MCP server**

   In one terminal, start Kerbal Space Program and enable the kRPC server (Protobuf over TCP).  Note the address and ports shown in the kRPC window.  In another terminal, run:

   ```sh
   # from the repo root
   uv run -m mcp_server.main
   ```

   The server will listen for incoming requests over stdio (for Codex integration) and handle script execution and tool calls.

3. **Register with Codex CLI (optional)**

   If you use [Codex CLI](https://github.com/openai/openai-codex-cli), add the MCP server so it can be launched on demand:

   ```sh
   codex mcp add krpc_docs -- uv run -m mcp_server.main --with krpc
   ```

4. **Connect to your game**

   When calling tools that interact with the game (execute scripts, fetch blueprints, etc.), provide the address and ports of your running KSP instance.  For example:

   ```
   Use krpc_docs to execute_script with code "print('hello'); print('SUMMARY: done')" and address "192.168.1.10" rpc_port 50000 stream_port 50001
   ```

## Detailed tool reference

### execute_script

Run short Python code snippets in a live KSP session.  The environment is pre‑configured as described above.  Scripts must include a `SUMMARY:` line to provide a machine‑parsable result; everything printed or logged becomes part of the transcript.

#### Example script: gravity turn

```py
# (No imports or krpc.connect – MCP injects conn, vessel, logging, etc.)
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
        vs  = flight.vertical_speed
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

### Blueprint & diagram tools

- `get_vessel_blueprint(address, rpc_port, stream_port) → blueprint`  
  Fetches the blueprint as a JSON object containing `meta`, `stages`, `engines`, and `parts` arrays.  Useful for reasoning about staging and part hierarchy.

- `get_part_tree(address, rpc_port, stream_port) → parts[]`  
  Returns a list of parts with parent/child relationships, stage, modules and resources.

- `get_blueprint_ascii(address, rpc_port, stream_port) → str`  
  Produces a concise, human‑readable summary of the vessel’s staging and key parts.

- `export_blueprint_diagram(address, rpc_port, stream_port, format='svg'|'png', out_dir=None)`  
  Generates a diagram of the vessel.  The result is saved to `artifacts/blueprints/` and made available via special resource URIs:

  - `resource://blueprints/last-diagram.svg`  – the latest SVG diagram
  - `resource://blueprints/last-diagram.png`  – JSON with a base64‑encoded PNG (requires Pillow)

### KSP Wiki & documentation search

Use these tools to gather knowledge about game mechanics or kRPC functions without leaving chat:

- `search_ksp_wiki(query: str, limit: int = 10)` – search KSP Wiki pages.
- `get_ksp_wiki_page(title: str, max_chars: int = 5000)` – retrieve the full text of a Wiki page (truncated to `max_chars`).
- `get_ksp_wiki_section(title: str, heading: str, max_chars: int = 3000)` – get a specific section of a Wiki page.
- `search_krpc_docs(query: str, k: int)` – search the local kRPC docs index for pages containing your query.
- `get_krpc_doc(url: str, max_chars: int)` – fetch and truncate a specific kRPC doc page.

### Playbooks & resources

- `resource://playbooks/vessel-blueprint-usage` – a markdown guide on interpreting the blueprint data, planning safe staging and burns, and common pitfalls.

Agents can fetch this resource to better understand the blueprint fields and to inform their mission planning.

## Building the knowledge bases

The MCP server includes pipelines for scraping and indexing the kRPC documentation.  These steps are only needed when the docs change; the repository ships with prebuilt JSONL files in `data/krpc_python_docs.jsonl`.  To regenerate the index:

1. **Scrape the docs**

   ```sh
   uv run scripts/scrape_krpc_docs.py  \
     --start https://krpc.github.io/krpc/python.html \
     --base  https://krpc.github.io/krpc/ \
     --out   data/krpc_python_docs.full.jsonl
   ```

2. **Filter to Python‑only pages and tutorials**

   ```sh
   uv run scripts/filter_python_only.py  \
     --infile  data/krpc_python_docs.full.jsonl \
     --outfile data/krpc_python_docs.jsonl
   ```

3. **Search the index** (optional sanity check)

   ```sh
   uv run scripts/search_krpc_index.py "autopilot" --k 5
   ```

These pipelines support Sphinx inventory files and gracefully fall back to a crawl if necessary.

## Project layout & development

- `scripts/` – utilities for scraping the docs, filtering pages and running CLI checks.
- `data/krpc_python_docs.jsonl` – the prebuilt dataset of kRPC docs.
- `krpc_index/` – search library for indexed docs.
- `mcp_server/` – the MCP server code and tool definitions (see `mcp_server/tools.py`).
- `artifacts/` – output directory for blueprint diagrams, cached by `export_blueprint_diagram`.

To contribute or customise the server, clone the repository, install dependencies, and modify the tools or pipelines as needed.  Pull requests are welcome!

---

> 🥪 **Experimental**: This project is under active development.  Use at your own risk and feel free to open issues or PRs if you encounter problems or have suggestions.
