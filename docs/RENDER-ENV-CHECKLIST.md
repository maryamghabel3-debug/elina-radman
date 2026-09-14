# Render Worker — Environment Checklist (M19)

`scripts/render_worker.py` reliability knobs. All have in-code defaults;
set them in the workflow (`render-worker.yml`) only if you need to deviate.

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `RENDER_WORKER_MAX_JOBS_PER_RUN` | `5` | Jobs processed per worker run before it exits, even if the queue still has jobs. The 5-minute cron picks the rest up. |
| `RENDER_WORKER_MAX_RUN_SECONDS` | `1500` (25 min) | Hard run-time budget. Keeps a run safely under the GitHub Actions 30-minute job limit. |
| `RENDER_JOB_TIMEOUT_SECONDS` | `900` (15 min) | Hard per-job timeout. On timeout the job is marked `FAILED` with `RENDER_TIMEOUT` (retried while attempts remain) and the owner is notified; the run continues with the next job. |
| `RENDER_STALE_JOB_MINUTES` | `30` | At the start of every run, jobs stuck in `IN_PROGRESS` with `started_at` older than this are recovered (see below). |

Existing variables (unchanged): `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
`SUPABASE_BUCKET_NAME`, `STUDIO_BOT_TOKEN`, `FREESOUND_API_KEY`,
`ELINA_FONT_PRIMARY_PATH`, `PUBLISH_LIVE_ENABLED`.

## Reliability behavior

- **Atomic claim.** Claiming a job is a conditional
  `UPDATE ... WHERE id=? AND status='QUEUED'`. Concurrent runners
  (cron overlap, manual dispatch during cron) can never claim the same job:
  the loser's update affects 0 rows and moves to the next candidate.
  Defense in depth: the workflow already sets
  `concurrency: {group: elina-render-worker, cancel-in-progress: false}`.
- **Multi-job runs.** A run processes up to `MAX_JOBS_PER_RUN` jobs (success,
  terminal failure, retryable failure, or timeout all count) and logs a run
  summary: `claimed / completed / failed_terminal / failed_retryable / timeouts`.
- **Exit-code policy (per run).** `0` = all claimed jobs processed
  (including expected terminal failures). `1` = any infrastructure error
  (DB/network/unexpected exception).
- **Stale job recovery.** At run start, `IN_PROGRESS` jobs older than
  `RENDER_STALE_JOB_MINUTES`:
  - `attempts < max_attempts` → back to `QUEUED` with
    `error_message=RECOVERED_FROM_STALE_IN_PROGRESS`
  - otherwise → `FAILED` with `RENDER_STALE_ABANDONED` + owner Telegram notice
  - Recovery uses a guarded conditional update
    (`status='IN_PROGRESS' AND started_at < cutoff`), so a job that
    legitimately just finished is never clobbered.

## How to recover a stuck job (manual)

Jobs are normally recovered automatically by the next worker run. To force
it sooner (Supabase SQL editor):

```sql
-- see what is stuck
SELECT id, content_id, status, started_at, attempts, max_attempts
FROM render_jobs
WHERE status = 'IN_PROGRESS'
  AND started_at < now() - interval '30 minutes';

-- requeue the ones that still have attempts left
UPDATE render_jobs
SET status = 'QUEUED',
    error_message = 'RECOVERED_FROM_STALE_IN_PROGRESS (manual)'
WHERE status = 'IN_PROGRESS'
  AND started_at < now() - interval '30 minutes'
  AND attempts < max_attempts;

-- abandon the exhausted ones
UPDATE render_jobs
SET status = 'FAILED',
    error_message = 'RENDER_STALE_ABANDONED (manual)',
    completed_at = now()
WHERE status = 'IN_PROGRESS'
  AND started_at < now() - interval '30 minutes'
  AND attempts >= max_attempts;
```

Or trigger the worker immediately: **Actions → Render Worker → Run workflow**
(recovery runs at the start of every run).

## Audio / SFX (M33)

- **Freesound is optional.** It is only used for *query-based* SFX plan
  entries (`plan_sfx: [{query: "..."}]`). Long renders should not depend on
  the live Freesound service.
- **Uploaded audio beds are preferred for final production renders.**
  Upload an audio file to the Studio Bot (any ELN-RAW audio content item)
  and reference it directly in the edit plan:

  ```json
  {"content_id": "ELN-RAW-...", "background_bed": true,
   "normalize_loudness": true, "gain_db": -22,
   "fade_in_sec": 2.0, "fade_out_sec": 3.0}
  ```

  or by raw storage key: `{"asset_key": "uploads/ambience.mp3", ...}`.
  These entries are downloaded from Supabase Storage and **bypass
  Freesound entirely** (no API key needed, no live search, deterministic).
  All timing/gain/fade/`background_bed`/`normalize_loudness` fields work
  exactly as for query-based SFX.
- **Error codes.** `SFX_ASSET_NOT_FOUND` (missing content item / no
  media_keys) and `SFX_INVALID_CONFIG` (e.g. `content_id` + `query` on one
  entry) are **terminal** — retrying will not help.
  `SFX_ASSET_DOWNLOAD_FAILED` (transient storage/network) is **retryable**.
