from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcp_server import executor_tools
from mcp_server.executor_tools import job_tools
from mcp_server.executor_tools.job_artifacts import job_artifact_path, job_resource_uri
from mcp_server.executor_tools.jobs import JobRegistry, JobStatus, job_registry
from mcp_server.executor_impl.core import _resolve_timeouts


class DummyConn:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _wait_for_completion(job_id: str, timeout: float = 5.0) -> None:
    job_registry.wait_for(job_id, timeout=timeout)
    state = job_registry.get_state(job_id)
    assert state is not None
    assert state.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)


def test_start_part_tree_job_creates_artifact(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("mcp_server.executor_tools.job_artifacts.JOB_ARTIFACTS_DIR", tmp_path, raising=False)
    dummy_conn = DummyConn()

    def fake_connect(address: str, rpc_port: int, stream_port: int, name: str | None, timeout: float) -> DummyConn:
        return dummy_conn

    def fake_part_tree(conn: DummyConn) -> dict[str, Any]:
        return {"parts": [{"id": 1}]}

    monkeypatch.setattr(job_tools, "connect_to_game", fake_connect)
    monkeypatch.setattr(job_tools.readers, "part_tree", fake_part_tree)

    payload = json.loads(
        job_tools.start_part_tree_job("1.2.3.4", rpc_port=1234, stream_port=2345, name="Test", timeout=1.0)
    )
    job_id = payload["job_id"]
    assert payload["status"] == "PENDING"

    _wait_for_completion(job_id)

    state = job_registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.SUCCEEDED
    assert state.result_resource == job_resource_uri(job_id)

    artifact = job_artifact_path(job_id)
    assert artifact.exists()
    data = json.loads(artifact.read_text())
    assert data["kind"] == "part_tree"
    assert data["result"]["parts"] == [{"id": 1}]


def test_start_stage_plan_job_passes_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("mcp_server.executor_tools.job_artifacts.JOB_ARTIFACTS_DIR", tmp_path, raising=False)
    dummy_conn = DummyConn()

    def fake_connect(address: str, rpc_port: int, stream_port: int, name: str | None, timeout: float) -> DummyConn:
        return dummy_conn

    captured_environment: list[str] = []

    def fake_stage_plan(conn: DummyConn, environment: str = "current") -> dict[str, Any]:
        captured_environment.append(environment)
        return {"env": environment, "stages": []}

    monkeypatch.setattr(job_tools, "connect_to_game", fake_connect)
    monkeypatch.setattr(job_tools.readers, "stage_plan_approx", fake_stage_plan)

    payload = json.loads(
        job_tools.start_stage_plan_job(
            "1.2.3.4",
            rpc_port=1111,
            stream_port=2222,
            name=None,
            timeout=2.0,
            environment="vacuum",
        )
    )
    job_id = payload["job_id"]
    _wait_for_completion(job_id)

    artifact = job_artifact_path(job_id)
    data = json.loads(artifact.read_text())
    assert data["kind"] == "stage_plan"
    assert data["params"]["environment"] == "vacuum"
    assert captured_environment == ["vacuum"]


def test_start_execute_script_job_creates_artifact(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("mcp_server.executor_tools.job_artifacts.JOB_ARTIFACTS_DIR", tmp_path, raising=False)

    def fake_run_execute_script(**kwargs):
        handle = kwargs.pop("job_handle", None)
        assert handle is not None
        handle.log("[stdout] hello world")
        return {
            "ok": True,
            "summary": "done",
            "transcript": "print\\nSUMMARY: done",
            "stdout": "print",
            "stderr": "",
            "error": None,
            "paused": True,
            "unpaused": False,
            "timing": {"exec_time_s": 1.0},
            "pre_pause_flight": None,
        }

    # Patch the core runner used by the job function.
    monkeypatch.setattr("mcp_server.executor_impl.core._run_execute_script", fake_run_execute_script)

    payload = json.loads(
        executor_tools.start_execute_script_job(
            "print('hi')",
            "127.0.0.1",
            rpc_port=50000,
            stream_port=50001,
            name="Test",
        )
    )
    job_id = payload["job_id"]
    _wait_for_completion(job_id)

    state = job_registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.SUCCEEDED
    assert state.result_resource == job_resource_uri(job_id)

    artifact = job_artifact_path(job_id)
    assert artifact.exists()
    data = json.loads(artifact.read_text())
    assert data["kind"] == "execute_script"


def test_start_execute_script_job_marks_failed_when_script_result_not_ok(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("mcp_server.executor_tools.job_artifacts.JOB_ARTIFACTS_DIR", tmp_path, raising=False)

    def fake_run_execute_script(**kwargs):
        handle = kwargs.pop("job_handle", None)
        assert handle is not None
        handle.log("[stderr] ZeroDivisionError: float division by zero")
        return {
            "ok": False,
            "summary": None,
            "transcript": "Traceback (most recent call last): ...",
            "stdout": "",
            "stderr": "ZeroDivisionError: float division by zero",
            "error": {"type": "ZeroDivisionError", "message": "float division by zero"},
            "paused": True,
            "unpaused": False,
            "timing": {"exec_time_s": 0.1},
            "pre_pause_flight": None,
            "follow_up": {"suggest_get_diagnostics": True},
        }

    # Patch the core runner used by the job function.
    monkeypatch.setattr("mcp_server.executor_impl.core._run_execute_script", fake_run_execute_script)

    payload = json.loads(
        executor_tools.start_execute_script_job(
            "1/0",
            "127.0.0.1",
            rpc_port=50000,
            stream_port=50001,
            name="Test",
        )
    )
    job_id = payload["job_id"]
    _wait_for_completion(job_id)

    state = job_registry.get_state(job_id)
    assert state is not None
    assert state.status is JobStatus.FAILED
    assert state.result_resource == job_resource_uri(job_id)

    artifact = job_artifact_path(job_id)
    assert artifact.exists()
    data = json.loads(artifact.read_text())
    assert data["kind"] == "execute_script"
    assert data["result"]["ok"] is False


def test_resolve_timeouts_preserves_soft_and_bumps_hard_when_needed():
    # hard watchdog should trail soft timeout by margin without altering soft
    soft, hard = _resolve_timeouts(timeout_sec=180.0, hard_timeout_sec=120.0, job_handle=None)
    assert soft == 180.0
    assert hard == 190.0


def test_transient_stream_error_detects_proactor_noise():
    jr = JobRegistry(max_workers=1)
    noisy = "ERROR Exception in callback ProactorBasePipeTransport._call_connection_lost"
    assert jr._transient_kind(noisy) == "benign_shutdown"
