Async kRPC Tooling Implementation Plan
=====================================

Context check:
- The server uses `mcp.server.fastmcp` (not the standalone `fastmcp` package), and tools run on the asyncio loop directly unless they are `async def`.
- All kRPC helpers go through `mcp_server/utils/krpc_helpers.open_connection` -> `krpc_utils.client.connect_to_game` (blocking).
- Most tools live in `mcp_server/general_tools.py` calling sync impls in `general_tools_impl/*`; start-job tools (e.g., `start_part_tree_job`, `start_execute_script_job`) already run in a ThreadPool via `executor_impl.jobs.JobRegistry`.
- Direct `execute_script` is sync and can run long; it has its own internal hard timeout, so it should be run off-loop but not clamped to the 60s Codex limit.

- [x] Add async wrappers (non-invasive to impls)
  - [x] Introduce a helper (`run_blocking(fn, *, timeout_sec=60)`) using `asyncio.to_thread` + `asyncio.wait_for` with optional cleanup (`mcp_server/utils/async_utils.py`).
  - [x] Add `async_open_connection` convenience that delegates to the blocking `connect_to_game` via the above helper and keeps the existing sync helper intact for job threads.
  - [x] Make per-call timeout configurable; default 60s for normal tools, allow `None`/custom per call.

- [x] Wrap tool entry points (non-job kRPC tools)
  - [x] Ensure sync `@mcp.tool` functions run off-loop via the tool manager: `InjectionAwareToolManager` now runs sync tools in a worker thread with a 60s default hard timeout.
  - [x] Preserve the existing argument parsing/convert_result behavior while honoring the 60s default for normal tools.
  - [x] Keep a short allowlist exempt from the 60s clamp when they have their own safety nets (e.g., `execute_script` `hard_timeout_sec`; start-job tools stay exempt).

- [x] Preserve long-running start-job / job-backed tools
- [x] Leave `start_part_tree_job`, `start_execute_script_job` (and other job_registry-backed starters) as-is; they already execute in a ThreadPool and are exempt from the 60s clamp.
  - [x] Treat direct `execute_script` as exempt from the 60s clamp; it relies on its internal `hard_timeout_sec`.

- [x] Injection compatibility and plumbing
  - [x] `InjectionAwareToolManager` now awaits thread-backed sync tools; async tools still run inline. No signature changes required.
  - [x] Injection merge behavior unchanged (content/structured tuple handling remains the same).

- [x] Tests / harness
  - [x] Add a small async test/harness that mocks a slow call to confirm the timeout path trips and the event loop remains responsive.
  - [x] Add a smoke check that a start-job tool (or `execute_script` with its own `hard_timeout_sec`) is not forcibly cut off by the new default wrapper.

- [x] Docs
  - [x] Document the new async wrapper behavior, the 60s default for normal tools, and the explicit exemptions (job starters, `execute_script` watchdog) in `README.md` or a short ops note.
  - [x] Mention the timeout override parameter so users can tune per call.
