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


def test_get_job_status_includes_wall_time_elapsed_for_running_job():
    stop_event = threading.Event()

    def job(_handle):
        while not stop_event.is_set():
            time.sleep(0.02)

    job_id = job_registry.create_job(job)

    # Wait until it is RUNNING so started_at is set.
    deadline = time.time() + 2.0
    payload = None
    while time.time() < deadline:
        payload = json.loads(get_job_status(job_id))
        if payload["status"] == "RUNNING":
            break
        time.sleep(0.02)

    assert payload is not None
    assert payload["status"] == "RUNNING"
    assert "wall_time_elapsed_s" in payload
    assert payload["wall_time_elapsed_s"] >= 0.0

    stop_event.set()
    job_registry.wait_for(job_id, timeout=5.0)


def test_get_job_status_warp_suffix_adds_warp_progress(monkeypatch):
    import mcp_server.libraries as libs

    stop_event = threading.Event()

    def job(_handle):
        while not stop_event.is_set():
            time.sleep(0.02)

    job_id = job_registry.create_job(
        job,
        metadata={
            "kind": "warp",
            "params": {
                "ut": 123.0,
                "lead_time_s": 3.0,
                "address": "127.0.0.1",
                "rpc_port": 50000,
                "stream_port": 50001,
                "timeout": 0.01,
            },
        },
    )

    sentinel = {"universal_time_s": 1.0, "warp_rate_effective": 50.0}
    monkeypatch.setattr(libs, "_warp_monitor", lambda **kwargs: sentinel)

    payload = json.loads(get_job_status(f"{job_id}_warp"))
    assert payload["canonical_job_id"] == job_id
    assert payload["job_id_suffix"] == "_warp"
    assert payload["warp_progress"] == sentinel

    stop_event.set()
    job_registry.wait_for(job_id, timeout=5.0)


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


def test_benign_shutdown_traceback_is_suppressed():
    job_id = job_registry.create_job(lambda handle: None)
    job_registry.wait_for(job_id)

    # Simulate a common benign asyncio/proactor shutdown traceback on Windows.
    # This often shows up as an "Exception in callback ..." header followed by a traceback.
    job_registry.append_log(job_id, "ERROR    Exception in callback base_events.py:1821", stream="stderr")
    job_registry.append_log(job_id, "Traceback (most recent call last):", stream="stderr")
    job_registry.append_log(job_id, '  File "asyncio\\\\proactor_events.py", line 123, in _call_connection_lost', stream="stderr")
    job_registry.append_log(
        job_id,
        "OSError: [WinError 10038] An operation was attempted on something that is not a socket",
        stream="stderr",
    )

    payload = json.loads(get_job_status(job_id))
    assert payload["status"] == "SUCCEEDED"
    assert payload["traceback_suppressed"] is True
    assert payload["log_stream_warning"] is False
    assert all("Traceback (most recent call last):" not in line for line in payload["logs"])


def test_get_job_status_strips_ansi_sequences_by_default():
    job_id = job_registry.create_job(lambda handle: None)
    job_registry.wait_for(job_id)

    msg = (
        "\x1b[34mINFO\x1b[0m Terminating session: "
        "\x1b]8;id=1;file://C:\\tmp\\server.py\x1b\\"
        "server.py"
        "\x1b]8;;\x1b\\"
        " done"
    )
    job_registry.append_log(job_id, msg, stream="stderr")

    payload = json.loads(get_job_status(job_id))
    assert payload["logs_sanitized"] is True
    combined = "\n".join(payload["logs"])
    assert "\x1b" not in combined
    assert "INFO" in combined
    assert "server.py" in combined


def test_get_job_status_raw_suffix_preserves_ansi_sequences():
    job_id = job_registry.create_job(lambda handle: None)
    job_registry.wait_for(job_id)

    msg = "\x1b[31mERROR\x1b[0m boom"
    job_registry.append_log(job_id, msg, stream="stderr")

    payload = json.loads(get_job_status(f"{job_id}_raw"))
    assert payload["logs_sanitized"] is False
    combined = "\n".join(payload["logs"])
    assert "\x1b" in combined
