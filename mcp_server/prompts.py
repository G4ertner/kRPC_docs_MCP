from __future__ import annotations

from pathlib import Path

from .server import mcp


MASTER_PROMPT_FILE = "SCRIBE_Master_Prompt_KSP_MCP.md"


def _load_master_prompt() -> str:
    """
    Load the SCRIBE master prompt from the repository root Markdown file.

    This lets you edit the prompt in-place without touching server code.
    """
    # mcp_server/ -> project root
    root = Path(__file__).resolve().parents[1]
    path = root / MASTER_PROMPT_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:  # pragma: no cover
        return f"Master prompt could not be loaded: {e}\nExpected at: {path}"
    return text


# Register as a resource (always available as a fallback)
@mcp.resource("resource://prompts/scribe-master")
def get_scribe_master_prompt_resource() -> str:
    """Return the SCRIBE master prompt as a resource."""
    return _load_master_prompt()


# Try to register as an MCP Prompt (preferred). FastMCP exposes a `prompt` API.
def _register_master_prompt() -> None:
    register = getattr(mcp, "prompt", None)
    if callable(register):
        try:
            # Use the decorator programmatically to avoid import-time failures
            register(
                "scribe_master",
                description="System primer for kRPC MCP agent (read first)",
            )(lambda: _load_master_prompt())
        except Exception:
            # If prompt registration fails, the resource remains available.
            pass


_register_master_prompt()

