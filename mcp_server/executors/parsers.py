from __future__ import annotations

import json
import re
from typing import Any, Dict, Tuple


EXEC_META_PREFIX = "[[[EXEC_META]]] "


def split_stdout_and_meta(stdout: str) -> Tuple[str, Dict[str, Any] | None]:
    """
    Extract a trailing executor meta JSON line if present.
    Returns (stdout_without_meta, meta_dict|None).
    """
    lines = stdout.splitlines()
    meta: Dict[str, Any] | None = None
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if line.startswith(EXEC_META_PREFIX):
            payload = line[len(EXEC_META_PREFIX) :].strip()
            try:
                meta = json.loads(payload)
            except Exception:
                meta = None
            # drop this line from transcript
            lines.pop(i)
            break
    return "\n".join(lines), meta


def parse_summary(stdout: str) -> str | None:
    """
    Heuristic: find the last occurrence of 'SUMMARY:' and return that line and the remainder.
    If not present, return None. Works with multi-line triple-quoted blocks when printed.
    """
    idx = stdout.rfind("SUMMARY:")
    if idx == -1:
        return None
    return stdout[idx:].strip()


def extract_error_from_stderr(stderr: str) -> Dict[str, Any] | None:
    """Best-effort traceback parser for Python exceptions to return {type, message, line}."""
    if not stderr:
        return None
    # Simple regex for the last exception line: 'ValueError: something'
    m = re.search(r"^([A-Za-z_][\w\.]*)\s*:\s*(.*)$", stderr.strip().splitlines()[-1])
    err_type = m.group(1) if m else "RuntimeError"
    msg = m.group(2) if m else stderr.strip().splitlines()[-1]
    # Line number hint from traceback lines like 'File "<user_code>", line 12'
    ln = None
    for line in stderr.splitlines():
        mm = re.search(r"File\s+\"<user_code>\",\s+line\s+(\d+)", line)
        if mm:
            try:
                ln = int(mm.group(1))
            except Exception:
                ln = None
    return {"type": err_type, "message": msg, "line": ln}

