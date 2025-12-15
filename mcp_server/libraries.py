from __future__ import annotations

import sys
import re
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parent.parent
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    from mcp_server.mcp_context import mcp
    from mcp_server.library_impl import krpc_docs, ksp_wiki, snippets
    from mcp_server.general_tools_impl.status_and_time import _orbital_ascent_monitor, _warp_monitor
    from mcp_server.utils.ansi_utils import strip_ansi
    from mcp_server.utils.json_utils import dumps as json_dumps
    from mcp_server.utils.krpc_helpers import DEFAULT_KRPC_ADDRESS
else:
    from .mcp_context import mcp
    from .library_impl import krpc_docs, ksp_wiki, snippets
    from .general_tools_impl.status_and_time import _orbital_ascent_monitor, _warp_monitor
    from .utils.ansi_utils import strip_ansi
    from .utils.json_utils import dumps as json_dumps
    from .utils.krpc_helpers import DEFAULT_KRPC_ADDRESS


def _copy_doc(target, source):
    target.__doc__ = getattr(source, "__doc__", None)
    return target


_CANONICAL_JOB_ID_RE = re.compile(r"^([0-9a-fA-F]{32})(.*)$")


def _split_job_id(requested_job_id: str) -> tuple[str, str]:
    """
    Split a possibly-suffixed job id into (canonical_job_id, suffix).

    The canonical job id is the 32-hex UUID used by the internal JobRegistry.
    Suffixes are an out-of-band convention used by some tool wrappers to request
    extra logging/monitoring payloads during polling.

    If the string does not begin with a 32-hex prefix, it is treated as-is.
    """
    match = _CANONICAL_JOB_ID_RE.match(requested_job_id or "")
    if not match:
        return requested_job_id, ""
    return match.group(1), match.group(2)


def _parse_job_id_suffix(suffix: str) -> set[str]:
    """
    Parse a suffix like '_asc_raw' into {'_asc', '_raw'}.

    Suffix is an out-of-band convention used by some tools to request extra
    payloads or toggle log formatting for get_job_status polling.
    """
    if not suffix:
        return set()
    parts = [p for p in suffix.split("_") if p]
    return {f"_{part}" for part in parts}


@mcp.tool()
def search_krpc_docs(query: str, limit: int = 10) -> str:
    """
    Search the kRPC Python docs (plus Welcome/Getting Started/Tutorials) and return the top results.
    When to use:
        - Explore kRPC APIs, examples, or concepts before implementing a call.
    Args:
        query: Free-text query
        limit: Max results to return (default 10)
    Returns:
        A newline-delimited list of formatted results with title and URL and a short snippet.
    """
    return krpc_docs.search_krpc_docs_impl(query=query, limit=limit)


@mcp.tool()
def get_krpc_doc(url: str, max_chars: int = 5000) -> str:
    """
    Retrieve a kRPC doc page by URL and return its text content. Use with URLs from search_krpc_docs.
    When to use:
        - Pull the full text of a doc page to inspect details and examples.
    Args:
        url: Exact page URL from the dataset
        max_chars: Truncate returned content to this many characters (default 5000)
    Returns:
        Title, URL, and cleaned page text (truncated) with basic headings metadata.
    """
    return krpc_docs.get_krpc_doc_impl(url=url, max_chars=max_chars)



@mcp.tool()
def get_job_status(job_id: str) -> str:
    """
    Poll the status of a background job started by tools such as start_execute_script_job.

    Usage pattern:
        1. Call a job-starting tool (e.g., start_execute_script_job/start_stage_plan_job) to get a job_id.
        2. Poll get_job_status(job_id) until "status" == "SUCCEEDED" (or FAILED for troubleshooting).
        3. When SUCCEEDED, call read_resource on "result_resource" (resource://jobs/<id>.json) to fetch the artifact.
        4. If FAILED, inspect logs/error, address the issue, and optionally restart the job.

    Returns:
        JSON string with fields:
            - job_id: the requested identifier
            - status: PENDING | RUNNING | SUCCEEDED | FAILED | CANCELLED (or UNKNOWN when not found)
            - created_at / started_at / finished_at timestamps (ISO 8601, UTC) when available
            - logs: accumulated stdout/stderr/log entries
            - result_resource: resource URI containing the job output, if produced
            - error: error description when failed or unknown
            - metadata: any job-specific metadata stored at creation time
            - ok: boolean convenience flag (false when FAILED, CANCELLED, or UNKNOWN)
        Notes:
            - Logs are returned with ANSI escape sequences stripped by default for easier parsing.
            - To return raw logs, append the suffix "_raw" to the job_id (e.g., "<id>_raw").
            - To include live warp telemetry + ETA (best-effort), append the suffix "_warp" (e.g., "<id>_warp").
    """

    requested_job_id = job_id
    canonical_job_id, suffix = _split_job_id(requested_job_id)
    suffix_flags = _parse_job_id_suffix(suffix)

    base_payload = krpc_docs.get_job_status_impl(job_id=canonical_job_id)

    # Optional extra telemetry payload requested via suffix convention.
    extra: dict = {}
    if "_asc" in suffix_flags:
        extra["game_logging"] = _orbital_ascent_monitor()

    if "_warp" in suffix_flags:
        # Best-effort extra payload for warp jobs (and for debugging warp state generally).
        try:
            target_ut = None
            try:
                meta = base_payload.get("metadata") or {}
                if isinstance(meta, dict) and meta.get("kind") == "warp":
                    params = meta.get("params") or {}
                    if isinstance(params, dict) and params.get("ut") is not None:
                        ut = float(params["ut"])
                        lead = float(params.get("lead_time_s") or 0.0)
                        target_ut = ut - max(0.0, lead)
            except Exception:
                target_ut = None

            addr = DEFAULT_KRPC_ADDRESS
            rpc = 50000
            stream = 50001
            nm = None
            timeout = 2.0
            try:
                if isinstance(base_payload.get("metadata"), dict):
                    params = (base_payload["metadata"].get("params") or {}) if isinstance(base_payload["metadata"].get("params"), dict) else {}
                    addr = params.get("address", addr)
                    rpc = int(params.get("rpc_port", rpc))
                    stream = int(params.get("stream_port", stream))
                    nm = params.get("name", nm)
                    timeout = float(params.get("timeout", timeout))
            except Exception:
                pass

            extra["warp_progress"] = _warp_monitor(
                address=addr,
                rpc_port=rpc,
                stream_port=stream,
                name=nm,
                timeout=min(2.0, timeout),
                target_ut=target_ut,
            )
        except Exception as exc:
            extra["warp_progress_error"] = str(exc)

    payload = base_payload | extra

    if "_raw" not in suffix_flags:
        payload["logs"] = [strip_ansi(line) for line in payload.get("logs", [])]
        payload["logs_sanitized"] = True
    else:
        payload["logs_sanitized"] = False

    # Echo the exact identifier the caller used, but also expose the canonical id.
    payload["job_id"] = requested_job_id
    payload["canonical_job_id"] = canonical_job_id
    payload["job_id_suffix"] = suffix
    return json_dumps(payload)


 



@mcp.tool()
def cancel_job(job_id: str, reason: str | None = None) -> str:
    """
    Request cancellation of a running background job (if supported).

    When to use:
        - Abort a long-running job that is no longer needed or must stop for safety reasons. Follow up by reverting/loading the appropriate checkpoint before proceeding.

    Returns:
        JSON: { ok: bool, message: str }
    """
    canonical_job_id, _suffix = _split_job_id(job_id)
    return krpc_docs.cancel_job_impl(job_id=canonical_job_id, reason=reason)


@mcp.tool()
def search_ksp_wiki(query: str, limit: int = 10) -> str:
    """
    Search the KSP Wiki (English) and return the top results.
    When to use:
        - Gather background on KSP mechanics, parts, or gameplay concepts.

    Args:
        query: Search query text
        limit: Max results to return (default 10)
    Returns:
        Newline-delimited items: "- Title — URL" with a short snippet below.
    """
    return ksp_wiki.search_ksp_wiki_impl(query=query, limit=limit)



@mcp.tool()
def get_ksp_wiki_page(title: str, max_chars: int = 5000) -> str:
    """
    Fetch a KSP Wiki page in plain text (English).
    When to use:
        - Read a complete article for deeper context or guidance.

    Args:
        title: Page title (e.g., "Delta-v")
        max_chars: Truncate returned text to this many characters (default 5000)
    Returns:
        Title, canonical URL, and plain text (truncated).
    """
    return ksp_wiki.get_ksp_wiki_page_impl(title=title, max_chars=max_chars)



@mcp.tool()
def get_ksp_wiki_section(title: str, heading: str, max_chars: int = 3000) -> str:
    """
    Fetch a specific section from a KSP Wiki page (English).
    When to use:
        - Retrieve a focused subsection (e.g., a usage guide) quickly.

    Args:
        title: Page title (e.g., "Maneuver node")
        heading: Section heading to fetch (case-insensitive)
        max_chars: Max characters to return (default 3000)
    Returns:
        Title + section heading + canonical URL and the section text, or a not-found message.
    """
    return ksp_wiki.get_ksp_wiki_section_impl(title=title, heading=heading, max_chars=max_chars)



@mcp.tool()
def snippets_search(query: str, k: int = 10, mode: str = "keyword", and_logic: bool = False, category: str | None = None, exclude_restricted: bool = False, rerank: bool = False) -> str:
    """
    Search the snippet library.

    Args:
      query: free-text query
      k: number of results
      mode: 'keyword' or 'hybrid'
      and_logic: when true, use AND semantics for keyword token combination
      category: optional category filter
      exclude_restricted: exclude GPL/AGPL/LGPL when true
      rerank: re-score Top-M with an LLM (when available) in hybrid mode
    Returns:
      JSON: { items: [...], source: {...} }
    """
    return snippets.snippets_search_impl(query=query, k=k, mode=mode, and_logic=and_logic, category=category, exclude_restricted=exclude_restricted, rerank=rerank)


@mcp.tool()
def snippets_get(id: str, include_code: bool = False) -> str:
    """
    Search the snippet library.

    Args:
      query: free-text query
      k: number of results
      mode: 'keyword' or 'hybrid'
      and_logic: when true, use AND semantics for keyword token combination
      category: optional category filter
      exclude_restricted: exclude GPL/AGPL/LGPL when true
      rerank: re-score Top-M with an LLM (when available) in hybrid mode
    Returns:
      JSON: { items: [...], source: {...} }
    """
    return snippets.snippets_get_impl(id=id, include_code=include_code)


@mcp.tool()
def snippets_resolve(id: str | None = None, name: str | None = None, max_bytes: int = 25000, max_nodes: int = 25) -> str:
    """
    Resolve a snippet (by id or module.qualname) into a paste-ready bundle including dependencies.

    Returns JSON: { ok, bundle_code?, include_ids?, unresolved?, truncated?, stats? }.
    """
    return snippets.snippets_resolve_impl(id=id, name=name, max_bytes=max_bytes, max_nodes=max_nodes)



@mcp.tool()
def snippets_search_and_resolve(query: str, k: int = 10, mode: str = "hybrid", rerank: bool = False, and_logic: bool = False, category: str | None = None, exclude_restricted: bool = False, max_bytes: int = 25000, max_nodes: int = 25) -> str:
    """
    Search and resolve top-1 result into a code bundle.

    Returns JSON with top result metadata and bundle fields.
    """
    return snippets.snippets_search_and_resolve_impl(query=query, k=k, mode=mode, rerank=rerank, and_logic=and_logic, category=category, exclude_restricted=exclude_restricted, max_bytes=max_bytes, max_nodes=max_nodes)


@mcp.resource("resource://snippets/usage")
def get_snippets_usage() -> str:
    return snippets.get_snippets_usage_impl()
