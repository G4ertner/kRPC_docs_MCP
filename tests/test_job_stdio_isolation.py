from __future__ import annotations

import json
import sys
import threading
import time

from mcp_server.executor_tools.jobs import job_registry
from mcp_server.libraries import get_job_status


def test_global_stderr_does_not_leak_into_job_logs(capsys):
    """
    Regression test for W002: job runner must not capture unrelated stderr from other threads.

    Background:
      - Using contextlib.redirect_stderr inside a worker thread mutates sys.stderr globally.
      - On Windows, asyncio/proactor shutdown noise can be emitted by the server while a job runs.
      - That noise must not appear in the job's logs payload.
    """

    ready = threading.Event()
    stop = threading.Event()

    def job(handle):
        handle.log("job started")
        ready.set()
        while not stop.is_set():
            time.sleep(0.01)
        handle.log("job finished")

    job_id = job_registry.create_job(job)
    assert ready.wait(timeout=2.0)

    sentinel = "GLOBAL_STDERR_SENTINEL_DO_NOT_CAPTURE"
    sys.stderr.write(sentinel + "\n")
    sys.stderr.flush()

    stop.set()
    job_registry.wait_for(job_id, timeout=5.0)

    payload = json.loads(get_job_status(job_id))
    combined = "\n".join(payload["logs"])
    assert sentinel not in combined

    # Ensure sentinel still hit pytest's own capture so we're not "swallowing" stderr globally.
    captured = capsys.readouterr()
    assert sentinel in captured.err

