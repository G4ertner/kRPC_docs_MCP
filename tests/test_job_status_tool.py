from __future__ import annotations

import json
import time
import threading

from mcp_server.executor_tools.jobs import JobStatus, job_registry
from mcp_server.libraries import cancel_job, get_job_status


def _wait_for_status(job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    collected: list[str] = []
    while time.time() < deadline:
        payload = json.loads(get_job_status(job_id))
        collected.extend(payload["logs"])
        if payload["status"] in {"SUCCEEDED", "FAILED"}:
            payload["logs_collected"] = collected
            return payload
        time.sleep(0.05)
    raise AssertionError("Job did not finish in time")


def test_get_job_status_reports_completed_job():
    def job(handle):
        handle.log("ping")
        print("stdout line")
        handle.set_result_resource("resource://demo/result.json")

    job_id = job_registry.create_job(job)
    payload = _wait_for_status(job_id)
    assert payload["status"] == "SUCCEEDED"
    assert payload["job_id"] == job_id
    assert payload["result_resource"] == "resource://demo/result.json"
    assert payload["ok"] is True
    assert any("ping" in entry for entry in payload["logs_collected"])


def test_get_job_status_unknown_job_returns_error():
    payload = json.loads(get_job_status("missing-job"))
    assert payload["status"] == "UNKNOWN"
    assert payload["ok"] is False
    assert "Job not found" in payload["error"]


def test_connection_reset_noise_is_suppressed():
    # Create a short job so state exists in the registry.
    job_id = job_registry.create_job(lambda handle: None)
    job_registry.wait_for(job_id)

    noisy = "ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host"
    job_registry.append_log(job_id, noisy, stream="stderr")

    payload = json.loads(get_job_status(job_id))
    assert payload["log_stream_warning"] is True
    assert all("ConnectionResetError" not in line for line in payload["logs"])


def test_logs_are_incremental_and_numbered():
    def job(handle):
        handle.log("first")
        handle.log("second")

    job_id = job_registry.create_job(job)
    job_registry.wait_for(job_id)

    first = json.loads(get_job_status(job_id))
    assert first["log_cursor"] == 2
    assert any("1:" in line and "first" in line for line in first["logs"])
    assert any("2:" in line and "second" in line for line in first["logs"])

    # No new entries → only the continuing header
    second = json.loads(get_job_status(job_id))
    assert second["log_cursor"] == 2
    assert second["logs"][0].startswith("continuing logs:")
    assert len(second["logs"]) == 1

    # Inject another log and verify numbering continues
    job_registry.append_log(job_id, "third", stream="log")
    third = json.loads(get_job_status(job_id))
    assert third["log_cursor"] == 3
    assert any("3:" in line and "third" in line for line in third["logs"])


def test_get_job_status_echoes_requested_id_with_suffix():
    job_id = job_registry.create_job(lambda handle: None)
    job_registry.wait_for(job_id)

    requested = f"{job_id}_atm"
    payload = json.loads(get_job_status(requested))

    assert payload["status"] == "SUCCEEDED"
    assert payload["job_id"] == requested
    assert payload["canonical_job_id"] == job_id
    assert payload["job_id_suffix"] == "_atm"


def test_cancel_job_accepts_suffixed_id():
    stop_event = threading.Event()
    callback_ready = threading.Event()

    def job(handle):
        handle.register_cancel_callback(stop_event.set)
        callback_ready.set()
        while not stop_event.is_set():
            handle.log("running")
            time.sleep(0.02)

    job_id = job_registry.create_job(job)
    assert callback_ready.wait(timeout=2.0)
    resp = json.loads(cancel_job(f"{job_id}_atm"))
    assert resp["ok"] is True

    job_registry.wait_for(job_id, timeout=5.0)
    state = job_registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.CANCELLED
