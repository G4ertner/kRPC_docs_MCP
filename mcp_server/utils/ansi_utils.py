from __future__ import annotations

import re


_CSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_OSC_RE = re.compile(r"\x1B\].*?(?:\x07|\x1B\\)")
_DCS_RE = re.compile(r"\x1BP.*?\x1B\\")


def strip_ansi(text: str) -> str:
    """
    Remove common ANSI escape sequences (CSI/OSC/DCS) from text.

    Intended for normalizing logs for JSON transport and QA tooling.
    """
    if not text:
        return text
    # Order matters: OSC/DCS can contain '[', so remove those first.
    cleaned = _OSC_RE.sub("", text)
    cleaned = _DCS_RE.sub("", cleaned)
    cleaned = _CSI_RE.sub("", cleaned)
    return cleaned
