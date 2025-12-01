from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport to serve (stdio by default)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host for SSE/HTTP transports (defaults to FastMCP settings)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for SSE/HTTP transports (defaults to FastMCP settings)",
    )
    parser.add_argument(
        "--mount-path",
        default=None,
        help="Optional mount path for SSE transport",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.host:
        mcp.settings.host = args.host
    if args.port:
        mcp.settings.port = args.port
    # Run Streamable HTTP transport in stateless mode so single HTTP calls don't need session IDs.
    mcp.settings.stateless_http = True
    mcp.run(transport=args.transport, mount_path=args.mount_path)


if __name__ == "__main__":
    main()
