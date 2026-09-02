import os
import time
from unittest.mock import MagicMock, patch

import pytest

import scripts.render_worker as rw
from agents.rendering.job_manager import RenderJobManager

pytestmark = pytest.mark.unit


def make_worker_mgr(jobs):
    """Mock RenderJobManager whose claim pops jobs in order."""
    mgr = MagicMock()
    queue = list(jobs)

    def claim():
        return queue.pop(0) if queue else None

    mgr.get_next_queued_job.side_effect = claim
    mgr.recover_stale_jobs.return_value = {"recovered": [], "abandoned": []}
    return mgr


ENV_DEFAULTS = {
    "RENDER_WORKER_MAX_JOBS_PER_RUN": "5",
    "RENDER_WORKER_MAX_RUN_SECONDS": "1500",
    "RENDER_JOB_TIMEOUT_SECONDS": "900",
    "RENDER_STALE_JOB_MINUTES": "30",
}


def job(i):
    return {"id": f"job-{i}", "content_id": f"ELN-{i}", "owner_chat_id": "12345"}


# === A. two concurrent claims on the same QUEUED job -> exactly one succeeds ===

def test_A_concurrent_claims_exactly_one_succeeds():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    for m in ("select", "eq", "order", "limit", "update"):
        setattr(mock_query, m, MagicMock(return_value=mock_query))

    job = {"id": "job-1", "status": "QUEUED", "content_id": "ELN-1"}
    select_win = MagicMock(); select_win.data = [job]
    update_win = MagicMock(); update_win.data = [{**job, "status": "IN_PROGRESS"}]
    # Loser: still saw the job as QUEUED (race window), its guarded update
    # affects 0 rows, then the queue is empty.
    select_lose = MagicMock(); select_lose.data = [job]
    update_lose = MagicMock(); update_lose.data = []
    select_empty = MagicMock(); select_empty.data = []

    mock_query.execute.side_effect = [
        select_win, update_win,      # runner 1 wins
        select_lose, update_lose,    # runner 2 loses the race
        select_empty,                # runner 2: no more candidates
    ]
    mgr = RenderJobManager(db=mock_db)

    winner = mgr.claim_next_job()
    loser = mgr.claim_next_job()

    assert winner is not None and winner["id"] == "job-1"
    assert loser is None  # zero-row update was NEVER treated as a claim


# === B. claim skips to next candidate when first conditional update = 0 rows ===

def test_B_claim_skips_to_next_candidate():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    for m in ("select", "eq", "order", "limit", "update"):
        setattr(mock_query, m, MagicMock(return_value=mock_query))

    job1 = {"id": "job-1", "status": "QUEUED"}
    job2 = {"id": "job-2", "status": "QUEUED"}
    select1 = MagicMock(); select1.data = [job1]
    update1 = MagicMock(); update1.data = []  # lost the race
    select2 = MagicMock(); select2.data = [job2]
    update2 = MagicMock(); update2.data = [{**job2, "status": "IN_PROGRESS"}]

    mock_query.execute.side_effect = [select1, update1, select2, update2]
    mgr = RenderJobManager(db=mock_db)

    claimed = mgr.claim_next_job()
    assert claimed is not None
    assert claimed["id"] == "job-2"


# === C. empty queue -> claim None, run summary claimed=0, exit 0 ===

def test_C_empty_queue_exit_0():
    mgr = make_worker_mgr([])
    with patch.object(rw, "RenderJobManager", return_value=mgr), \
         patch.dict(os.environ, ENV_DEFAULTS), \
         patch.object(rw, "send_telegram_message"):
        # Empty queue: main() returns normally (process exit code 0)
        result = rw.main()
    assert result is None  # no sys.exit -> clean exit 0
    assert mgr.get_next_queued_job.call_count == 1


# === D. worker processes up to MAX_JOBS_PER_RUN then stops ===

def test_D_max_jobs_per_run_stops_early():
    mgr = make_worker_mgr([job(1), job(2), job(3)])
    processed = []
    summary = rw.run_render_run(
        mgr, max_jobs=2, max_run_seconds=1500, job_timeout_seconds=900,
        process=lambda j: processed.append(j["id"]) or True,
    )
    assert summary["claimed"] == 2
    assert processed == ["job-1", "job-2"]
    # third job never claimed
    assert mgr.get_next_queued_job.call_count == 2
    assert summary["infra_error"] is False


# === E. worker stops when MAX_RUN_SECONDS exceeded (mock clock) ===

def test_E_run_time_budget_stops_claiming():
    mgr = make_worker_mgr([job(1), job(2)])
    clock_values = iter([0.0, 0.0, 1600.0, 1601.0])
    summary = rw.run_render_run(
        mgr, max_jobs=5, max_run_seconds=1500, job_timeout_seconds=900,
        clock=lambda: next(clock_values),
        process=lambda j: True,
    )
    assert summary["claimed"] == 1  # budget hit before claiming job 2
    assert summary["completed"] == 1
    assert summary["infra_error"] is False


# === F. one terminal failure + one success -> exit 0, summary correct ===

def test_F_terminal_failure_plus_success_exit_0():
    mgr = make_worker_mgr([job(1), job(2)])
    # Full main() path: job1 terminal failure (False), job2 success (True)
    # -> clean exit 0
    with patch.object(rw, "RenderJobManager", return_value=mgr), \
         patch.dict(os.environ, ENV_DEFAULTS), \
         patch.object(rw, "process_job", side_effect=[False, True]), \
         patch.object(rw, "send_telegram_message"):
        with pytest.raises(SystemExit) as exc:
            rw.main()
    assert exc.value.code in (0, None)

    # Summary counters via the loop directly
    mgr2 = make_worker_mgr([job(1), job(2)])
    outcomes2 = iter([False, True])
    summary = rw.run_render_run(
        mgr2, max_jobs=5, max_run_seconds=1500, job_timeout_seconds=900,
        process=lambda j: next(outcomes2),
    )
    assert summary["claimed"] == 2
    assert summary["completed"] == 1
    assert summary["failed_terminal"] == 1
    assert summary["failed_retryable"] == 0
    assert summary["infra_error"] is False  # -> main() would sys.exit(0)


# === G. one infrastructure exception -> infra_error, others still recorded ===

def test_G_infra_exception_marks_run_infra_error():
    mgr = make_worker_mgr([job(1), job(2)])

    def flaky(j):
        if j["id"] == "job-1":
            raise RuntimeError("DB connection lost")
        return True

    summary = rw.run_render_run(
        mgr, max_jobs=5, max_run_seconds=1500, job_timeout_seconds=900,
        process=flaky,
    )
    assert summary["infra_error"] is True  # -> main() would sys.exit(1)
    # job2 was still processed and recorded
    assert summary["claimed"] == 2
    assert summary["completed"] == 1
    assert summary["failed_retryable"] == 1  # "DB connection lost" is not terminal


# === H. job timeout -> RENDER_TIMEOUT marked, next job still processed ===

def test_H_job_timeout_marks_render_timeout_and_continues():
    mgr = make_worker_mgr([job(1), job(2)])

    def slow_then_fast(j):
        if j["id"] == "job-1":
            time.sleep(2)  # exceeds the 0.3s budget
        return True

    with patch.object(rw, "send_telegram_message") as mock_notify:
        summary = rw.run_render_run(
            mgr, max_jobs=5, max_run_seconds=1500, job_timeout_seconds=0.3,
            process=slow_then_fast,
        )
    assert summary["timeouts"] == 1
    assert summary["completed"] == 1  # job2 still processed
    assert summary["claimed"] == 2
    assert summary["infra_error"] is False
    # job1 marked FAILED with RENDER_TIMEOUT (retryable while attempts remain)
    fail_calls = [c[0] for c in mgr.mark_failed.call_args_list]
    assert fail_calls and fail_calls[0][0] == "job-1"
    assert "RENDER_TIMEOUT" in fail_calls[0][1]
    # Persian owner notification sent
    assert mock_notify.call_count == 1
    assert "RENDER_TIMEOUT" in mock_notify.call_args[0][1]


# === I. stale IN_PROGRESS job with attempts < max -> re-QUEUED ===

def test_I_stale_job_requeued():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    for m in ("select", "eq", "lt", "update"):
        setattr(mock_query, m, MagicMock(return_value=mock_query))

    stale = {
        "id": "job-stale", "content_id": "ELN-X", "owner_chat_id": "1",
        "attempts": 1, "max_attempts": 3, "status": "IN_PROGRESS",
        "started_at": "2020-01-01T00:00:00+00:00",
    }
    select_res = MagicMock(); select_res.data = [stale]
    update_res = MagicMock(); update_res.data = [{**stale, "status": "QUEUED"}]
    mock_query.execute.side_effect = [select_res, update_res]

    mgr = RenderJobManager(db=mock_db)
    out = mgr.recover_stale_jobs(stale_minutes=30)

    assert len(out["recovered"]) == 1 and out["abandoned"] == []
    payload = mock_query.update.call_args[0][0]
    assert payload["status"] == "QUEUED"
    assert payload["error_message"] == "RECOVERED_FROM_STALE_IN_PROGRESS"
    # guarded conditional update: status + started_at cutoff
    mock_query.eq.assert_any_call("status", "IN_PROGRESS")
    mock_query.lt.assert_called()


# === J. stale IN_PROGRESS job with attempts >= max -> FAILED RENDER_STALE_ABANDONED ===

def test_J_stale_job_abandoned_at_max_attempts():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    for m in ("select", "eq", "lt", "update"):
        setattr(mock_query, m, MagicMock(return_value=mock_query))

    stale = {
        "id": "job-dead", "content_id": "ELN-Y", "owner_chat_id": "1",
        "attempts": 3, "max_attempts": 3, "status": "IN_PROGRESS",
        "started_at": "2020-01-01T00:00:00+00:00",
    }
    select_res = MagicMock(); select_res.data = [stale]
    update_res = MagicMock(); update_res.data = [{**stale, "status": "FAILED"}]
    mock_query.execute.side_effect = [select_res, update_res]

    mgr = RenderJobManager(db=mock_db)
    out = mgr.recover_stale_jobs(stale_minutes=30)

    assert out["recovered"] == [] and len(out["abandoned"]) == 1
    payload = mock_query.update.call_args[0][0]
    assert payload["status"] == "FAILED"
    assert payload["error_message"] == "RENDER_STALE_ABANDONED"
    assert "completed_at" in payload


# === K. fresh IN_PROGRESS job is NOT touched by recovery ===

def test_K_fresh_in_progress_job_not_touched():
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.client.table.return_value = mock_query
    for m in ("select", "eq", "lt", "update"):
        setattr(mock_query, m, MagicMock(return_value=mock_query))

    # The DB filter (status='IN_PROGRESS' AND started_at < cutoff) returns
    # nothing: the only IN_PROGRESS job started recently.
    select_res = MagicMock(); select_res.data = []
    mock_query.execute.return_value = select_res

    mgr = RenderJobManager(db=mock_db)
    out = mgr.recover_stale_jobs(stale_minutes=30)
    assert out == {"recovered": [], "abandoned": []}
    mock_query.update.assert_not_called()


# === L. run summary logged with all counters (incl. stale recovery) ===

def test_L_stale_abandoned_notifies_owner(caplog):
    mgr = make_worker_mgr([])
    abandoned_job = {"id": "job-old", "content_id": "ELN-OLD", "owner_chat_id": "777"}
    mgr.recover_stale_jobs.return_value = {
        "recovered": [{"id": "job-r"}], "abandoned": [abandoned_job],
    }
    with patch.object(rw, "send_telegram_message") as mock_notify, \
         caplog.at_level("INFO", logger="RenderWorker"):
        summary = rw.run_render_run(
            mgr, max_jobs=5, max_run_seconds=1500, job_timeout_seconds=900,
            process=lambda j: True,
        )
    assert summary["claimed"] == 0
    mock_notify.assert_called_once()
    chat_id, text = mock_notify.call_args[0]
    assert chat_id == "777"
    assert "RENDER_STALE_ABANDONED" in text
