# from __future__ import annotations

# import argparse
# import sys
# from pathlib import Path


# def _ensure_repo_root_on_path() -> None:
#     repo_root = Path(__file__).resolve().parent.parent
#     repo_root_str = str(repo_root)
#     if repo_root_str not in sys.path:
#         sys.path.insert(0, repo_root_str)


# if __package__ in (None, ""):
#     _ensure_repo_root_on_path()
#     from mcp_server.mcp_context import mcp
#     from mcp_server import libraries  # noqa: F401 - register documentation/snippet tools
#     from mcp_server import playbooks  # noqa: F401 - register playbook resources
#     from mcp_server import prompts    # noqa: F401 - register master prompt
#     from mcp_server import general_tools  # noqa: F401 - register general supporting tools
#     from mcp_server import executor_tools  # noqa: F401 - register execute_script tool
# else:
#     from .mcp_context import mcp
#     from . import libraries  # noqa: F401 - register documentation/snippet tools
#     from . import playbooks  # noqa: F401 - register playbook resources
#     from . import prompts    # noqa: F401 - register master prompt
#     from . import general_tools  # noqa: F401 - register general supporting tools
#     from . import executor_tools  # noqa: F401 - register execute_script tool


# def _parse_args() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(description="Run the GeePT FastMCP server")
#     parser.add_argument(
#         "--transport",
#         choices=["stdio", "sse", "streamable-http"],
#         default="stdio",
#         help="Transport to serve (stdio by default)",
#     )
#     parser.add_argument(
#         "--host",
#         default=None,
#         help="Host for SSE/HTTP transports (defaults to FastMCP settings)",
#     )
#     parser.add_argument(
#         "--port",
#         type=int,
#         default=None,
#         help="Port for SSE/HTTP transports (defaults to FastMCP settings)",
#     )
#     parser.add_argument(
#         "--mount-path",
#         default=None,
#         help="Optional mount path for SSE transport",
#     )
#     return parser.parse_args()


# def main() -> None:
#     args = _parse_args()
#     if args.host:
#         mcp.settings.host = args.host
#     if args.port:
#         mcp.settings.port = args.port
#     # Run Streamable HTTP transport in stateless mode so single HTTP calls don't need session IDs.
#     mcp.settings.stateless_http = True
#     mcp.run(transport=args.transport, mount_path=args.mount_path)




# if __name__ == "__main__":
#     main()
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


if __package__ in (None, ""):
    _ensure_repo_root_on_path()
    from mcp_server.mcp_context import mcp
    from mcp_server import libraries  # noqa: F401 - register documentation/snippet tools
    from mcp_server import playbooks  # noqa: F401 - register playbook resources
    from mcp_server import prompts    # noqa: F401 - register master prompt
    from mcp_server import general_tools  # noqa: F401 - register general supporting tools
    from mcp_server import executor_tools  # noqa: F401 - register execute_script tool
else:
    from .mcp_context import mcp
    from . import libraries  # noqa: F401 - register documentation/snippet tools
    from . import playbooks  # noqa: F401 - register playbook resources
    from . import prompts    # noqa: F401 - register master prompt
    from . import general_tools  # noqa: F401 - register general supporting tools
    from . import executor_tools  # noqa: F401 - register execute_script tool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the GeePT FastMCP server")

    # 👉 Default to streamable-http for Codex / MCP clients
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="streamable-http",
        help="Transport to serve (streamable-http by default)",
    )

    # 👉 Default host/port so `uv run -m mcp_server.main` is enough
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE/HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5500,
        help="Port for SSE/HTTP transports (default: 5500)",
    )

    # Optional mount-path; default to /mcp which is what most clients expect
    parser.add_argument(
        "--mount-path",
        default="/mcp",
        help="Optional mount path for SSE/HTTP transport (default: /mcp)",
    )

    return parser.parse_args()


def _maybe_terminate_sibling_servers(
    *,
    keyword: str = "mcp_server.main",
    port: int | None = None,
) -> List[int]:
    """
    Terminate other python processes running the same server module.

    Prefers psutil when available; falls back to a Windows netstat/taskkill approach when not.
    """
    try:
        import psutil  # type: ignore
    except Exception:
        psutil = None  # type: ignore[assignment]

    current_pid = os.getpid()
    terminated: List[int] = []

    def _is_match(cmdline: Iterable[str]) -> bool:
        joined = " ".join(cmdline)
        return keyword in joined or "mcp_server/main.py" in joined or "mcp_server\\main.py" in joined

    if psutil is not None:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            pid = proc.info.get("pid")
            if pid is None or pid == current_pid:
                continue
            cmdline = proc.info.get("cmdline") or []
            if _is_match(cmdline):
                try:
                    if port is not None:
                        conns = proc.net_connections(kind="inet")
                        if not any(getattr(c.laddr, "port", None) == port for c in conns if getattr(c, "laddr", None)):
                            continue
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        continue
                terminated.append(pid)
        return terminated

    if os.name != "nt" or port is None:
        return []

    # Windows fallback when psutil isn't available in the environment (e.g. venv missing deps).
    # 1) Find PIDs LISTENING on the target port via netstat.
    # 2) For each PID, read its command line via PowerShell CIM and only kill when it matches our module.
    try:
        netstat_out = subprocess.check_output(["netstat", "-ano", "-p", "TCP"], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return []

    pids: set[int] = set()
    needle = f":{port}"
    for line in netstat_out.splitlines():
        line = line.strip()
        if not line.startswith("TCP"):
            continue
        # Example:
        # TCP    127.0.0.1:5500         0.0.0.0:0              LISTENING       10784
        parts = [p for p in line.split() if p]
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        state = parts[3]
        pid_str = parts[4]
        if needle not in local_addr:
            continue
        if state.upper() != "LISTENING":
            continue
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        if pid != current_pid:
            pids.add(pid)

    for pid in sorted(pids):
        try:
            cmd = (
                f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"
            )
            cmdline = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()
        except Exception:
            continue
        if not cmdline:
            continue
        if keyword not in cmdline and "mcp_server/main.py" not in cmdline and "mcp_server\\main.py" not in cmdline:
            continue
        try:
            subprocess.check_output(["taskkill", "/PID", str(pid), "/F"], text=True, stderr=subprocess.STDOUT)
        except Exception:
            continue
        terminated.append(pid)

    return terminated


def main() -> None:
    args = _parse_args()

    terminated = _maybe_terminate_sibling_servers(port=args.port)
    if terminated:
        print(f"Terminated {len(terminated)} existing GeePT MCP server instance(s): {terminated}")

    # Apply settings only if relevant
    if args.host:
        mcp.settings.host = args.host
    if args.port:
        mcp.settings.port = args.port

    # Run Streamable HTTP transport in stateless mode so single HTTP calls don't need session IDs.
    # If you ever support stdio/sse in the same binary, you can guard this:
    # if args.transport in ("sse", "streamable-http"):
    mcp.settings.stateless_http = True

    mcp.run(transport=args.transport, mount_path=args.mount_path)


if __name__ == "__main__":
    main()
