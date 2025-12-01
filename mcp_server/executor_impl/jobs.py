"""
Thread-safe background job registry used by the MCP server.

The registry is responsible for:
* Creating unique job identifiers.
* Tracking lifecycle timestamps and statuses.
* Capturing stdout/stderr emitted by job callables.
* Exposing helper methods for future job starter tools.
"""

from __future__ import annotations

import contextlib
import io
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


def _utc_now() -> float:
    return time.time()


def _format_timestamp(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class JobState:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=_utc_now)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    logs: List[str] = field(default_factory=list)
    result_resource: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False
    log_stream_warning: bool = False

    def as_dict(self) -> Dict[str, Any]:
        """Serialize the job state with ISO timestamps for JSON transport."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": _format_timestamp(self.created_at),
            "started_at": _format_timestamp(self.started_at),
            "finished_at": _format_timestamp(self.finished_at),
            "logs": list(self.logs),
            "result_resource": self.result_resource,
            "error": self.error,
            "metadata": dict(self.metadata),
            "cancel_requested": self.cancel_requested,
            "log_stream_warning": self.log_stream_warning,
        }


class _LogStream(io.TextIOBase):
    """File-like helper that streams stdout/stderr into the job log."""

    def __init__(self, registry: "JobRegistry", job_id: str, stream_name: str) -> None:
        super().__init__()
        self._registry = registry
        self._job_id = job_id
        self._stream_name = stream_name
        self._buffer = ""

    def write(self, s: str) -> int:  # type: ignore[override]
        if not s:
            return 0
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._registry.append_log(self._job_id, line.rstrip("\r"), stream=self._stream_name)
        return len(s)

    def flush(self) -> None:  # type: ignore[override]
        if self._buffer:
            self._registry.append_log(self._job_id, self._buffer.rstrip("\r"), stream=self._stream_name)
            self._buffer = ""


class JobHandle:
    """Handle passed to job callables so they can report progress safely."""

    def __init__(self, registry: "JobRegistry", job_id: str) -> None:
        self._registry = registry
        self.job_id = job_id

    def log(self, message: str) -> None:
        self._registry.append_log(self.job_id, message, stream="log")

    def set_result_resource(self, uri: str) -> None:
        self._registry.set_result_resource(self.job_id, uri)

    def register_cancel_callback(self, callback: Callable[[], None]) -> None:
        """Register a callable that will be invoked if the job is cancelled."""
        self._registry.register_cancel_callback(self.job_id, callback)


class JobRegistry:
    """Central registry that manages background job execution and state."""

    def __init__(self, max_workers: int = 4) -> None:
        self._jobs: Dict[str, JobState] = {}
        self._futures: Dict[str, Future[Any]] = {}
        self._cancel_callbacks: Dict[str, Callable[[], None]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-runner")

    def create_job(self, func: Callable[[JobHandle], Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        job_id = uuid.uuid4().hex
        state = JobState(job_id=job_id, metadata=metadata or {})
        with self._lock:
            self._jobs[job_id] = state
            self._cancel_callbacks[job_id] = lambda: None
        future = self._executor.submit(self._run_job, job_id, func)
        with self._lock:
            self._futures[job_id] = future
        return job_id

    def _run_job(self, job_id: str, func: Callable[[JobHandle], Any]) -> None:
        handle = JobHandle(self, job_id)
        self._set_status(job_id, JobStatus.RUNNING)
        try:
            func(handle)
        except Exception as exc:
            self.fail_job(job_id, str(exc))
        else:
            self.complete_job(job_id)
        finally:
            self._clear_cancel_callback(job_id)

    def complete_job(self, job_id: str) -> None:
        self._finish_job(job_id, JobStatus.SUCCEEDED)

    def fail_job(self, job_id: str, error: str) -> None:
        self._finish_job(job_id, JobStatus.FAILED, error=error)

    def _finish_job(self, job_id: str, status: JobStatus, error: Optional[str] = None) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return
            if state.status == JobStatus.CANCELLED and status != JobStatus.CANCELLED:
                return
            state.status = status
            state.finished_at = _utc_now()
            state.error = error

    def _set_status(self, job_id: str, status: JobStatus) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return
            state.status = status
            if status == JobStatus.RUNNING:
                state.started_at = _utc_now()

    def append_log(self, job_id: str, message: str, stream: str) -> None:
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        entry = f"[{timestamp}] [{stream}] {message}"
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return
            if self._is_transient_stream_error(message):
                state.log_stream_warning = True
                return
            state.logs.append(entry)

    @staticmethod
    def _is_transient_stream_error(message: str) -> bool:
        msg = message.lower()
        if "exception in callback" in msg and "proactor" in msg:
            return True
        if "connectionreseterror" in msg:
            return True
        if "forcibly closed by the remote host" in msg:
            return True
        if "connection reset by peer" in msg:
            return True
        if "_call_connection_lost" in msg:
            return True
        if "broken pipe" in msg:
            return True
        return False

    def set_result_resource(self, job_id: str, uri: str) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state:
                state.result_resource = uri

    def register_cancel_callback(self, job_id: str, callback: Callable[[], None]) -> None:
        with self._lock:
            self._cancel_callbacks[job_id] = callback

    def _clear_cancel_callback(self, job_id: str) -> None:
        with self._lock:
            self._cancel_callbacks.pop(job_id, None)

    def get_state(self, job_id: str) -> Optional[JobState]:
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return None
            return JobState(
                job_id=state.job_id,
                status=state.status,
                created_at=state.created_at,
                started_at=state.started_at,
                finished_at=state.finished_at,
                logs=list(state.logs),
                result_resource=state.result_resource,
                error=state.error,
                metadata=dict(state.metadata),
                log_stream_warning=state.log_stream_warning,
            )

    def wait_for(self, job_id: str, timeout: Optional[float] = None) -> None:
        future: Optional[Future[Any]]
        with self._lock:
            future = self._futures.get(job_id)
        if future is None:
            raise KeyError(f"Unknown job_id: {job_id}")
        try:
            future.result(timeout=timeout)
        except TimeoutError:
            raise
        except Exception:
            # The exception is already captured inside the job state.
            pass

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    def cancel_job(self, job_id: str, reason: str = "Cancelled by user request") -> Dict[str, Any]:
        callback: Optional[Callable[[], None]] = None
        with self._lock:
            state = self._jobs.get(job_id)
            if not state:
                return {"ok": False, "message": "Job not found."}
            if state.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
                return {"ok": False, "message": f"Job already finished with status {state.status.value}."}
            state.status = JobStatus.CANCELLED
            state.finished_at = _utc_now()
            state.error = reason
            state.cancel_requested = True
            callback = self._cancel_callbacks.get(job_id)
        self.append_log(job_id, reason, stream="log")
        if callback:
            try:
                callback()
            except Exception:
                pass
        return {"ok": True, "message": "Job cancellation requested."}


# Shared registry instance used by the MCP server.
job_registry = JobRegistry()
