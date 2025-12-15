from __future__ import annotations

import sys
import threading
import time

from mcp_server.executor_tools.jobs import JobRegistry, JobStatus


def test_job_lifecycle_success():
    registry = JobRegistry(max_workers=1)

    def job(handle):
        handle.log("starting work")
        print("hello from stdout")
        handle.set_result_resource("resource://demo/result.json")

    job_id = registry.create_job(job, metadata={"kind": "demo"})
    registry.wait_for(job_id, timeout=5)
    state = registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.SUCCEEDED
    assert state.result_resource == "resource://demo/result.json"
    assert state.started_at is not None
    assert state.finished_at is not None
    assert any("stdout" in line for line in state.logs)
    assert any("starting work" in line for line in state.logs)
    assert state.metadata["kind"] == "demo"
    registry.shutdown()


def test_job_failure_captures_error_and_stderr():
    registry = JobRegistry(max_workers=1)

    def job(_handle):
        print("things went boom", file=sys.stderr)
        raise RuntimeError("kaboom")

    job_id = registry.create_job(job)
    registry.wait_for(job_id, timeout=5)
    state = registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.FAILED
    assert "kaboom" in (state.error or "")
    assert any("stderr" in line and "things went boom" in line for line in state.logs)
    registry.shutdown()


def test_cancel_job_marks_state_and_runs_callback():
    registry = JobRegistry(max_workers=1)
    stop_event = threading.Event()
    callback_triggered = []

    def job(handle):
        def cancel_cb():
            callback_triggered.append(True)
            stop_event.set()
        handle.register_cancel_callback(cancel_cb)
        while not stop_event.is_set():
            handle.log("waiting for cancel")
            time.sleep(0.05)

    job_id = registry.create_job(job)
    resp = registry.cancel_job(job_id)
    assert resp["ok"]
    registry.wait_for(job_id, timeout=5)
    state = registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.CANCELLED
    assert callback_triggered
    registry.shutdown()


def test_job_handle_exposes_cancel_requested_flag():
    registry = JobRegistry(max_workers=1)
    stop_event = threading.Event()

    def job(handle):
        while not stop_event.is_set():
            if handle.is_cancel_requested():
                stop_event.set()
                return
            time.sleep(0.01)

    job_id = registry.create_job(job)
    resp = registry.cancel_job(job_id)
    assert resp["ok"]
    registry.wait_for(job_id, timeout=5)
    state = registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.CANCELLED
    registry.shutdown()
