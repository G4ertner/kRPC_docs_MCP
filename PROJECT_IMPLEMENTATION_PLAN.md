# **Project Implementation Plan: kRPC MCP Server for KSP Autonomous Agent**

This document outlines the **step-by-step project plan** for building, testing, and deploying the **MCP server that enables AI-controlled mission execution in Kerbal Space Program (KSP)**.  
It includes **technical milestones**, **automated and manual test plans**, and **status indicators** for tracking progress.

---

## ✅ **Phase 0 — Current State & Context (Completed)**

### Summary of Achievements
- The project repository **`G4ertner/kRPC_docs_MCP`** is set up and integrated with `uv` for dependency management.
- Core MCP server structure has been implemented with:
  - **mcp_server/** package containing `main.py`, `server.py`, and supporting modules.
  - **Wiki client** for querying the **KSP wiki** and **kRPC documentation**.
  - Basic **tool definitions** for structured MCP responses.
- The initial **architecture flow** (as shown in your FigJam/JPEG plan) is documented and mapped.

**Status:** ✅ Completed  
**Verification:**  
- Manual: `python -m mcp_server.main` runs successfully.  
- Automated: Basic unit tests confirming server startup and endpoint registration pass.

---

## **Phase 1 — Core MCP Infrastructure (In Progress)**

### Objective
Establish a fully functional MCP server that exposes structured, testable endpoints for:
- Knowledge retrieval  
- Game interaction (via kRPC)  
- Script execution  

### Tasks

#### **Step 1.1 — Define MCP Tool Schemas (✅ Done)**
Define each tool’s input/output schema as JSON objects in `tools.py`.

**Manual Test:**
- Run `python mcp_server/tools.py` to print available schemas.  
- Confirm schema matches expected MCP tool structure.

**Automated Test:**
- `pytest tests/test_schema_validation.py` — validates schema syntax, required fields, and proper JSON serialization.

---

#### **Step 1.2 — Implement Knowledge Tools (kRPC Docs + Wiki)** ✅ Done
Connect to the **KSP Wiki API** and **kRPC documentation source**, parse pages, and return structured summaries.

**Features:**
- `query(page_name)` — searches for a page.  
- `get(page_slug)` — retrieves parsed structured data (text, tables, infoboxes).  

**Manual Test:**
- Run `python scripts/ksp_wiki_cli.py Mun` and confirm results.  
- Query “Orbit” or “Thrust-to-weight ratio” — ensure clean markdown or JSON return.

**Automated Test:**
- Mock HTTP requests with `pytest + responses` to validate:
  - Response structure integrity  
  - Error handling for missing pages  
  - Caching logic (if implemented)

---

#### **Step 1.3 — Implement Prompting & Instruction Layer (🔄 In Progress)**
Create standardized “Primer Prompts” accessible as MCP functions.

**Features:**
- Main mission prompt template  
- Sub-prompts for:
  - General setup information  
  - Script execution protocol  
  - Debug/logging conventions

**Manual Test:**
- Invoke `get_primer("launch")` and verify that it returns properly formatted markdown.  

**Automated Test:**
- Ensure that each prompt type can be serialized and injected into a Codex CLI call.  
- Validate that keywords (`always use log statements`, `pause after run`, etc.) appear in the returned prompt.

---

#### **Step 1.4 — Implement kRPC Communication Tools (✅ Core Done)**
Live tools for telemetry, navigation, staging, and utilities — exposed via MCP.

**Implemented (read-only unless noted):**
- Connection helper: `connect_to_game(address, rpc_port, stream_port, name?, timeout?)`
- Status snapshot: `get_status_overview` (vessel, environment, flight, orbit, time, attitude, aero, nodes)
- Telemetry: `get_vessel_info`, `get_environment_info`, `get_flight_snapshot`, `get_orbit_info`, `get_time_status`, `get_attitude_status`, `get_aero_status`
- Engines & resources: `get_engine_status`, `get_resource_breakdown`, `get_power_status`
- Surface/camera/waypoints: `get_surface_info`, `get_camera_status`, `list_waypoints`
- Action groups: `get_action_groups_status`
- Targeting + navigation: `list_bodies`, `set_target_body`, `list_vessels`, `set_target_vessel`, `clear_target`, `get_targeting_info`, `get_navigation_info` (phase angle + next AN/DN times)
- Maneuver nodes (I/O): `list_maneuver_nodes`, `list_maneuver_nodes_detailed`, `set_maneuver_node`, `update_maneuver_node`, `delete_maneuver_nodes`, `warp_to`
- Staging & Δv: `get_staging_info` (raw per-stage), `get_stage_plan(environment=current|sea_level|vacuum)` (stock-like grouping, per-segment Δv/TWR)

**Remaining (deferred):**
- `take_screenshot` (see Screenshot/Images Strategy update below)
- `save_game_state`, `load_game_state` (evaluate safe hooks; otherwise manual)

**Manual Test:**
- Connect and call each tool against a live KSP+kRPC instance; verify against HUD and Map View.

**Automated Test:**
- Thin stubs with mocked kRPC objects to validate shape and key computations (e.g., Δv, burn time, phase angle, AN/DN bisection).

---

#### **Step 1.5 — Build Python Script Execution Pipeline (🧩 To Do)**
Pipeline dynamically modifies Python scripts generated by the LLM before running them.

**Execution Flow:**
1. Accept raw Python code (no imports).  
2. Automatically inject:
   - kRPC connector  
   - Pause handler  
   - End-of-script pause logic  
3. Execute code in a sandbox.  
4. Capture stdout/stderr/logs.  

**Manual Test:**
- Submit a short script (e.g., `print("test")`).  
- Confirm it’s wrapped with the connector and pause logic automatically.  
- Verify the game pauses correctly.

**Automated Test:**
- Use `pytest subprocess` to run sandbox execution with mock scripts.  
- Validate safe termination and log output parsing.

---

#### **Step 1.6 — Maneuver Planning Tools (✅ Batches 1–2; ✅ Batch 3 initial)**
High-level compute helpers that return node proposals (agent reviews → sets node → warps → executes via script pipeline).

**Batch 1 (done):**
- `compute_burn_time(dv_m_s, environment)` — simple and Tsiolkovsky burn-time estimates
- `compute_circularize_node(at='apoapsis'|'periapsis')`
- `compute_plane_change_nodes()` — AN/DN candidates with normal Δv

**Batch 2 (done):**
- `compute_raise_lower_node(kind='apoapsis'|'periapsis', target_alt_m)` — single-burn Hohmann leg
- `update_maneuver_node(index?, ut?, prograde?, normal?, radial?)`
- (Stub) `compute_rendezvous_phase_node` — to be implemented (phasing math)

**Batch 3 (added):**
- `compute_transfer_window_to_body(body)` — moon and interplanetary windows (with robust fallbacks)
- `compute_ejection_node_to_body(body, parking_alt_m, environment)` — coarse ejection Δv at window

**Next:**
- Implement `compute_rendezvous_phase_node` (period/phase matching), and add optional “one-shot” transfer planner (plan→set→warp).

## **Phase 2 — Integration and Feedback Loop (Planned)**

### Objective
Connect all modules to form a continuous mission loop:  
**Plan → Query → Execute → Pause → Evaluate → Continue**

### Maneuver Node Playbook Resource (New)
- Add a guidance resource the agent can read to follow a sensible order when planning and setting nodes. Keeps control flow explicit and tool calls deterministic.
- Resource: `resource://playbooks/maneuver-node`
  - Content (draft, also exposed as `resource://playbooks/maneuver-node`):
    1) Read status: `get_status_overview` (orbit, time, mass), `get_stage_plan(env)`
    2) Navigation context: `get_navigation_info` (phase angle, AN/DN)
    3) Choose goal: circularize | plane change | raise/lower Ap/Pe | transfer
    4) Plan: use `compute_*` helper (burn time, UT anchor, pro/normal/radial)
    5) Set: `set_maneuver_node(ut, prograde, normal, radial)`
    6) (Optional) Warp: `warp_to(ut - burn_time/2)`
    7) Execute burn (Python execution pipeline)
    8) Verify orbit; delete nodes when done

---

#### **Step 2.1 — Integration: LLM ↔ MCP (To Do)**
Create an interface for the Codex CLI or equivalent LLM to:
- Send structured requests  
- Receive telemetry/log data  
- Issue follow-up commands  

**Manual Test:**
- Run a simulated mission: “Launch to 10km altitude.”  
- Confirm loop continues until target altitude is achieved.

**Automated Test:**
- Simulate LLM commands using JSON payloads.  
- Validate correct sequence of tool invocations and responses.

---

#### **Step 2.2 — Automatic Pause Handling in Game (To Do)**
Implement a signal-based or RPC-based system to automatically pause KSP after each script execution.

**Manual Test:**
- Observe in-game behavior — game pauses after execution.  
- Ensure player/agent must manually resume (or trigger next LLM step).

**Automated Test:**
- Mock pause trigger and confirm proper game state change message.

---

#### **Step 2.3 — Error Feedback Loop (To Do)**
Provide structured error feedback (tracebacks, logs, and parsed exceptions) back to the LLM for diagnosis.

**Manual Test:**
- Intentionally submit invalid Python code → confirm error feedback is clear.  
- Ensure LLM can interpret and correct mistakes.

**Automated Test:**
- Verify all raised exceptions contain standardized error objects:
  ```json
  {\"error\": {\"type\": \"RuntimeError\", \"message\": \"...\", \"line\": 42}}
  ```

---

## **Phase 3 — Mission Autonomy & Optimization (Future Scope)**

### Goals
- Support multi-phase missions with persistent context (launch → orbit → transfer → landing).  
- Add visual feedback (screenshots, telemetry graphs).  
- Allow user-defined mission macros.

---

#### **Step 3.1 — Context Persistence**
Implement session memory in MCP for multi-stage mission continuity.

**Test:**
- Execute “Launch → Orbit → Deploy satellite” as a continuous session.  
- Validate previous telemetry is referenced in subsequent actions.

---

#### **Step 3.2 — Advanced Tooling**
Introduce higher-level tools for:
- Maneuver planning  
- Delta-v optimization  
- Science data retrieval  

**Automated Test:**  
Simulate multi-node mission planning sequence with random seed data; verify correct propagation of telemetry and target vectors.

---

#### **Step 3.3 — Visualization Tools**
Integrate optional telemetry visualizations (using Matplotlib or Plotly) to generate graphs and mission summaries.

**Manual Test:**
- After flight, generate a graph of altitude vs time.  
- Verify saved as image in output directory.

---

## **Testing Framework Overview**

| Layer | Test Type | Tools |
|------|------------|-------|
| Unit Tests | Functional validation | `pytest`, `responses`, `mock` |
| Integration Tests | Server-to-agent loop | `pytest-asyncio`, `subprocess` |
| System Tests | Live with KSP | manual + log verification |
| Performance | Execution time, IPC overhead | `pytest-benchmark` |
| Safety | Sandboxed script runner | `pytest` with mocked file I/O |

---

## **Phase 4 — Documentation & Community Integration (Future)**

- Full `README` with setup guide and usage examples  
- Integration with OpenAI Codex CLI and Assistant API for mission automation  
- Community templates for “Mission Scenarios” and “Script Recipes”

---

### ✅ **Summary of Progress**
| Phase | Step | Description | Status |
|-------|------|--------------|---------|
| 0 | Project Setup | Repo structure, basic MCP server | ✅ Done |
| 1.1 | Tool Schemas | JSON-based input/output structure | ✅ Done |
| 1.2 | Knowledge Tools | Wiki + Docs fetch tools | ✅ Done |
| 1.3 | Prompting Layer | Primer prompts for mission setup | 🔄 In Progress |
| 1.4 | kRPC Tools | Live telemetry, staging, nav, nodes | ✅ Core Done |
| 1.6 | Maneuver Planning | Batches 1–2 complete; Batch 3 initial | ✅ Added |
| 1.5 | Script Execution Pipeline | Auto-injected code runner | 🧩 To Do |
| 2 | Integration & Feedback Loop | Full LLM → MCP → KSP round trip | 🧩 To Do |
| 3 | Mission Autonomy | Persistent sessions & optimization | 🧩 To Do |
| 4 | Docs & Community | Documentation, open source release | 🧩 To Do |

---

## Update — Screenshot/Images Strategy (take_screenshot)

Goal
- Provide the agent with visual context from KSP (screenshots) in a way that works well with MCP and different client capabilities.

Key Insight (FastMCP/MCP best practice)
- Tools should return small, JSON-serializable results; large/binary payloads (images) should be exposed as MCP resources with a proper mime type (e.g., image/png). A tool returns a resource URI; the client fetches the image via the resource.

Recommended Shape
- Tool: `take_screenshot() -> { uri, title, saved_path? }`
  - Returns a resource URI like `resource://screenshots/2025-10-19T16-45-12Z.png`.
- Resource: `resource://screenshots/{name}.png`
  - Returns PNG bytes with `mime=image/png` and an optional `filename`.

Capture Options on the KSP PC (hardest part)
1) Custom kRPC plugin (best)
   - Add a small Unity/C# kRPC service that calls Unity's ScreenCapture API.
   - Returns PNG bytes (or writes to disk and returns a path).
   - Pros: Robust, low-latency; Cons: Needs plugin build/deploy.
2) OS-level capture agent/script
   - A lightweight service on the KSP PC captures the KSP window (e.g., ffmpeg/Powershell/GDI+ on Windows) and writes to a shared folder.
   - The MCP tool on this machine reads from that shared folder and exposes the file via a resource.
   - Pros: No plugin; Cons: Folder sharing/security, timing windows.
3) KSP built-in F1 screenshot + folder watch (manual fallback)
   - Use KSP's F1 to save screenshots; MCP tool finds the latest file in the Screenshots directory and exposes it as a resource.
   - Pros: Minimal code; Cons: Requires manual input or a separate trigger path.

Client Considerations
- Image-capable clients (e.g., some desktop assistants) will render the resource automatically if it advertises `image/png`.
- Text-only clients (e.g., current Codex CLI) cannot display images inline. Provide:
  - A local `saved_path` so the user can open the file manually.
  - Optional text metadata (timestamp, dimensions) and a short caption.

Implementation Plan (deferred)
1) Decide capture method (prefer custom kRPC plugin; otherwise, OS capture + shared folder).
2) MCP: add a screenshots resource namespace and `take_screenshot` tool that returns a resource URI.
3) Optional: add a `list_screenshots(limit=N)` tool to browse recent images.
4) For CLI/testing: also save the PNG under `krpc-docs/screenshots/` and return the path + metadata.

Risk & Mitigation
- Network/file-permissions for shared-folder approach → document required permissions and path mapping.
- Large images → consider a `thumbnail` resource variant (downscaled PNG) for quick inspection.


### **Appendix A — Proposed Directory Structure**

```
kRPC_docs_MCP/
├─ mcp_server/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ server.py
│  ├─ tools.py
│  ├─ wiki_tools.py
│  ├─ ksp_wiki_client.py
│  ├─ executors/
│  │  ├─ __init__.py
│  │  ├─ runner.py                # sandboxed executor
│  │  ├─ injectors.py             # connector + pauses
│  │  └─ parsers.py               # stdout/stderr + error parsing
│  └─ krpc/
│     ├─ __init__.py
│     ├─ client.py                # connection, retries, telemetry
│     └─ tools.py                 # MCP-exposed kRPC tools
├─ scripts/
│  └─ ksp_wiki_cli.py
├─ tests/
│  ├─ test_schema_validation.py
│  ├─ test_wiki_tools.py
│  ├─ test_prompt_layer.py
│  ├─ test_krpc_tools.py
│  └─ test_executor_pipeline.py
├─ pyproject.toml
├─ uv.lock
└─ PROJECT_IMPLEMENTATION_PLAN.md
```

---

### **Appendix B — Example MCP Tool I/O (JSON Schemas)**

**`get_vessel_info` (output):**
```json
{
  \"vessel\": {
    \"name\": \"...\", \"mass\": 0.0, \"throttle\": 0.0,
    \"velocity\": {\"surface\": 0.0, \"orbital\": 0.0},
    \"altitude\": {\"surface\": 0.0, \"sea_level\": 0.0},
    \"stage\": {\"current\": 2, \"delta_v\": 1234.5}
  },
  \"environment\": {\"body\": \"Kerbin\", \"biome\": \"...\", \"atmosphere\": true},
  \"timestamp\": \"ISO8601\"
}
```

**`execute_script` (input):**
```json
{
  \"code\": \"print('hello')\",
  \"options\": {\"pause_on_end\": true, \"timeout_sec\": 60}
}
```

---

### **Appendix C — Primer Prompts (Snippets)**

- *Main*: “You are mission control for KSP. Always emit log statements, and after each execution expect the game to be paused for planning.”  
- *Setup*: “kRPC server is reachable at 127.0.0.1:50000. Use `connect_to_game` before requesting telemetry.”  
- *Execution*: “All Python scripts must avoid imports; the system injects connectors and pause handlers automatically.”
