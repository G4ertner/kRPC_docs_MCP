from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ..mcp_context import mcp
from ..utils.json_utils import dumps as json_dumps

_ENV_OVERRIDE = os.environ.get("KRPC_JOBS_ARTIFACT_DIR")
JOB_ARTIFACTS_DIR: Path = Path(_ENV_OVERRIDE) if _ENV_OVERRIDE else Path.cwd() / "artifacts" / "jobs"


def job_artifact_path(job_id: str) -> Path:
    return JOB_ARTIFACTS_DIR / f"{job_id}.json"


def save_job_artifact(job_id: str, payload: Dict[str, Any]) -> Path:
    path = job_artifact_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def job_resource_uri(job_id: str) -> str:
    return f"resource://jobs/{job_id}.json"


@mcp.resource("resource://jobs/{job_id}.json")
def get_job_artifact(job_id: str) -> str:
    """Return the JSON artifact saved for a background job, if available."""
    path = job_artifact_path(job_id)
    if not path.exists():
        return json_dumps({"error": f"Artifact for job {job_id} not found."})
    return path.read_text(encoding="utf-8")
