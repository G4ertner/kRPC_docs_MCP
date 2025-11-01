from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def _parse_env_line(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.startswith("export "):
        s = s[len("export "):].lstrip()
    if "=" not in s:
        return None
    key, val = s.split("=", 1)
    key = key.strip()
    val = val.strip()
    # Trim surrounding single/double quotes if present
    if (val.startswith("\"") and val.endswith("\"")) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return key, val


def load_env_defaults() -> Dict[str, str]:
    """
    Load environment variables from krpc-snippets/.env if present.
    Existing environment values take precedence and are not overwritten.
    Returns a mapping of keys that were set.
    """
    # This module lives at <repo>/krpc-snippets/krpc_snippets/utils/env.py
    # We want <repo>/krpc-snippets/.env
    base = Path(__file__).resolve().parents[2]
    env_path = base / ".env"
    set_vars: Dict[str, str] = {}
    try:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                kv = _parse_env_line(line)
                if not kv:
                    continue
                k, v = kv
                if k not in os.environ:
                    os.environ[k] = v
                    set_vars[k] = v
    except Exception:
        # Best-effort only; ignore parse/read errors
        pass
    return set_vars

