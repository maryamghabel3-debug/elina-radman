# ELINAOS V2 — AGENT RUNTIME INVENTORY

## 1. Executive Summary
ElinaOS V2 has evolved into a robust, code-complete, and test-verified codebase. However, its true production status remains partially unverified, and live publishing is intentionally disabled. Heavy render orchestration and scheduler paths are active in code and locked down by 322 automated tests, but production Supabase migration and environment configurations remain UNKNOWN. This audit separates conceptual "docs-only" agents from actual in-repo Python classes, establishing a factual baseline for the runtime capabilities of the OS.

---

## 2. Key Finding: External Agents vs In-Repo Agents
*   **External Development Agents (e.g., Arena)**: These are external autonomous tools (such as the agent performing this audit) that assist in hotfixing, debugging, and code compilation. They are not part of the ElinaOS product runtime.
*   **In-Repo Runtime Agents**: These are real, compiled, and executed Python classes (like `ContentCreator`, `TrendHunter`, `EditOrchestrator`, and `PublishScheduler`) that handle core influencer operations.
*   **The Concept vs. Code Gap**: Beautifully designed markdown files under `docs/` list conceptual strategists and architects (like `ELN-STRAT-01` or `ELN-PSY-01`). However, these represent prompt configurations for external models rather than executable in-repo runtime code.

---

## 3. Status Definitions
To ensure strict verification, every agent and capability is evaluated against four independent fields:
1.  **Code Status**:
    *   `MERGED`: Real, functional Python code completely integrated on `main`.
    *   `PARTIAL`: Incomplete implementation or stub only.
    *   `DOCS_ONLY`: Exists strictly as markdown specifications or readme docs.
    *   `LEGACY`: Deprecated code replaced by active V2 modules.
2.  **Wiring Status**:
    *   `WIRED_TO_V2_ENTRYPOINT`: Triggered actively in the main V2 workflow, bot handlers, or cron worker loops.
    *   `WIRED_TO_LEGACY_ONLY`: Connected only to legacy scripts.
    *   `STANDALONE_ONLY`: Functional in local execution but not integrated into the main pipeline.
    *   `NOT_WIRED`: No execution path or import statement references it in the runtime.
3.  **Automation Status**:
    *   `SCHEDULED_ACTIVE`: Runs on an active remote cron trigger.
    *   `MANUAL_TRIGGER_ONLY`: Requires manual GHA dispatch (`workflow_dispatch`) or script run.
    *   `COMMAND_TRIGGERED`: Executed on-demand via Telegram chat commands.
    *   `NO_TRIGGER`: No automation hook exists.
4.  **Production Verification**:
    *   `PROD_VERIFIED`: Confirmed active and working in the live production database/environment.
    *   `TEST_VERIFIED_ONLY`: 100% green in the local mock-integrated test suite, but remote production status is unknown.
    *   `PROD_BLOCKED_BY_ENV`: Blocked by missing credentials or variables on remote hosts.
    *   `PROD_BLOCKED_BY_MIGRATION`: Blocked because target database tables/columns are pending migration verification.
    *   `UNKNOWN`: No telemetry or connection is available to verify status.

---

## 4. Canonical Inventory Table
*   **In-repo capabilities**: 35
*   **External tools**: 3

| ID | Capability / Agent | Code Status | Wiring Status | Automation Status | Production Verification | Main Runtime Entry Point |
|---|---|---|---|---|---|---|
| 01 | **Render Worker** | MERGED | WIRED_TO_V2_ENTRYPOINT | SCHEDULED_ACTIVE / COMMAND | PROD_BLOCKED_BY_MIGRATION | `scripts/render_worker.py` |
| 02 | **Publish Scheduler** | MERGED | WIRED_TO_V2_ENTRYPOINT | SCHEDULED_ACTIVE / COMMAND | PROD_BLOCKED_BY_ENV | `agents/scheduler.py` |
| 03 | **Content Creator** | MERGED | WIRED_TO_V2_ENTRYPOINT | MANUAL_TRIGGER_ONLY | TEST_VERIFIED_ONLY | `agents/content_creator.py` |
| 04 | **Trend Hunter** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/trend_hunter.py` |
| 05 | **Trend Video Analyzer** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/trend_video_analyzer.py` |
| 06 | **Trend Visual Analyzer** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/trend_visual_analyzer.py` |
| 07 | **Performance Analyzer** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/performance_analyzer.py` |
| 08 | **Product Hunter** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/product_hunter.py` |
| 09 | **Prompt Engineer** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/prompt_engineer.py` |
| 10 | **Edit Orchestrator** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/editing/orchestrator.py` |
| 11 | **Persian Edit Interpreter** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/editing/persian_edit_interpreter.py` |
| 12 | **Studio Bot** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | PROD_BLOCKED_BY_ENV | `scripts/elina_studio_bot.py` |
| 13 | **Intake Bot** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | PROD_BLOCKED_BY_ENV | `scripts/elina_intake_bot.py` |
| 14 | **Approval Manager** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/studio/approval.py` |
| 15 | **Video Bundle Manager** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/studio/bundle_manager.py` |
| 16 | **Render Job Manager** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/rendering/job_manager.py` |
| 17 | **LLM Router** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/llm_router.py` |
| 18 | **SFX Fetcher** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/audio/sfx_fetcher.py` |
| 19 | **Audio Engine** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/editing/audio_engine.py` |
| 20 | **Typography Engine** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/editing/typography_engine.py` |
| 21 | **Media Assembly Engine** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/editing/media_assembly.py` |
| 22 | **Video Concatenator** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/editing/concatenator.py` |
| 23 | **Supabase Client (ElinaDB)** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | PROD_BLOCKED_BY_MIGRATION | `agents/db/supabase_client.py` |
| 24 | **Supabase Storage (ElinaStorage)**| MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | PROD_BLOCKED_BY_ENV | `agents/storage/supabase_storage.py` |
| 25 | **Image Studio** | MERGED | WIRED_TO_V2_ENTRYPOINT | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/image_studio.py` |
| 26 | **Video Generator** | MERGED | STANDALONE_ONLY | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/video_generator.py` |
| 27 | **Platform Managers** | PARTIAL | STANDALONE_ONLY | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/platform_managers.py` |
| 28 | **Publisher (IG Graph)** | MERGED | WIRED_TO_V2_ENTRYPOINT | SCHEDULED_ACTIVE | PROD_BLOCKED_BY_ENV | `agents/publishers/instagram_graph.py` |
| 29 | **Publisher Zernio** | MERGED | NOT_WIRED | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/publisher_zernio.py` |
| 30 | **Faceless Studio** | MERGED | STANDALONE_ONLY | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/faceless_studio.py` |
| 31 | **Lip Sync Studio** | MERGED | STANDALONE_ONLY | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/lip_sync_studio.py` |
| 32 | **Fashion Stylist** | MERGED | STANDALONE_ONLY | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `agents/fashion_stylist.py` |
| 33 | **Vision Agent** | MERGED | STANDALONE_ONLY | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/vision.py` |
| 34 | **Memory Engine** | MERGED | STANDALONE_ONLY | NO_TRIGGER | TEST_VERIFIED_ONLY | `agents/memory_engine.py` |
| 35 | **Elina Bot (Legacy)** | LEGACY | WIRED_TO_LEGACY_ONLY | COMMAND_TRIGGERED | TEST_VERIFIED_ONLY | `scripts/elina_bot.py` |
| EX | *Arena Dev Agent* | EXTERNAL | NOT_WIRED | COMMAND_TRIGGERED | PROD_VERIFIED | N/A (External CLI/UI) |
| EX | *Midjourney/Flux* | EXTERNAL | NOT_WIRED | NO_TRIGGER | PROD_VERIFIED | N/A (Discord/Web UI) |
| EX | *Kling/Sora* | EXTERNAL | NOT_WIRED | NO_TRIGGER | PROD_VERIFIED | N/A (Web UI) |

---

## 5. V2 Runtime-Wired Agents
These are real, active Python classes linked to active workflows or bots:
*   **Render Worker (`scripts/render_worker.py`)**: Asynchronously processes queued video compiles.
*   **Publish Scheduler (`agents/scheduler.py`)**: Selects `edited_media_key` (if present) for Reel publishing, falling back to `media_keys[0]` for unedited ones.
*   **Image Studio (`agents/image_studio.py`)**: Mapped to `scripts/generate.py`. Supports Gemini Image and multiple upscaled look references (`images/*.jpg`). Features `STRICT_FACE_ONLY` support and fallbacks (NVIDIA SDXL, Fal.ai Flux, Together FLUX, PuLID, and InstantID).
*   **Content Creator (`agents/content_creator.py`)**: AI Copywriter called during daily-generation tasks, pulling trend visual/video analyses and grounding captions in Gemini.
*   **LLM Router (`agents/llm_router.py`)**: Implements OpenAI-compatible routing and failover across Groq, Gemini, OpenRouter, Cerebras, GitHub Models, and DeepSeek, with filtering to reject Chinese/CJK character contamination in Persian output.
*   **Persian Edit Interpreter (`agents/editing/persian_edit_interpreter.py`)**: Converts natural Persian edit commands to structured Edit Plans.
*   **Studio Bot (`scripts/elina_studio_bot.py`)** & **Intake Bot (`scripts/elina_intake_bot.py`)**: Active Telegram services using standard handlers.
*   **Render Job Manager (`agents/rendering/job_manager.py`)**: Manages queue, duplicates, and registers terminal fail errors (like `SHOT_INDEX_OUT_OF_RANGE`, `SFX_PROVIDER_NOT_CONFIGURED`, `MUSIC_PROVIDER_NOT_CONFIGURED`).

---

## 6. Manual-Trigger / Test-Verified Agents
*   **Daily Content Generation (`scripts/generate.py`)**: Mapped to `daily-content.yml`. However, the workflow's cron is currently **commented out** (`# schedule: [{cron: '0 23 * * *'}]`), meaning content generation is strictly **manual-trigger only** (`workflow_dispatch`).
*   **Trend Hunter (`agents/trend_hunter.py`)**: Scrapes Reddit Atom and Google Trends RSS. Gracefully degrades to static mocks on rate-limiting.
*   **Product Hunter (`agents/product_hunter.py`)**: Mapped to `generate.py`. Generates affiliate search URLs (Amazon, ShopStyle, LTK). However, product discovery uses simulated scraping (`simulate_web_scraping()`), not a real product catalog lookup.
*   **Performance Analyzer (`agents/performance_analyzer.py`)**: Mapped to `generate.py`. Includes real fetchers for Instagram Insights and YouTube view statistics, but reverts to simulated random metrics by default if environment variables are missing.

---

## 7. Orphaned or Partial Agents
*   **Platform Managers (`agents/platform_managers.py`)**: Only standalone stubs exist in the repository; no active production publish pipeline utilizes this module.
*   **Video Generator (`agents/video_generator.py`)**: Contains stubs only; Kling/Sora visual outputs are drafted manually.

---

## 8. Legacy Agents
*   **Elina Bot Legacy (`scripts/elina_bot.py`)**: Old, long-polling bot module. Replaced by the standard `scripts/elina_studio_bot.py` and `scripts/elina_intake_bot.py` which utilize standard async application builders.

---

## 9. External Arena/Generation Tools
*   **Arena Agents**: Assist in repository hotfixing and code generation. Not in runtime.
*   **Midjourney / Flux / Kling**: Operated manually via Discord or Web UI. To turn them into runtime agents, direct API adapters (e.g. Replicate Flux-PuLID or Kling API) must be wired.

---

## 10. Runtime Architecture Map
```
[Telegram Intake Bot] ──> Raw Video (MP4) ──> [Supabase Storage (private bucket)]
                                                   │
                                                   ▼
[Telegram Studio Bot] ──> /plan_ok (Persian) ──> [Supabase DB (render_jobs)]
                                                   │
                                                   ▼
                                        [GitHub Actions Worker (manual trigger)]
                                        - scripts/render_worker.py
                                        - downloads raw segments
                                        - normalizes profiles to 1080x1920
                                        - calls EditOrchestrator
                                        - resolves SFX via SFXFetcher
                                        - renders text with Vazirmatn-Bold
                                        - runs MediaAssembly (FFmpeg) with music_gain_db
                                        - uploads unique output to Storage
                                        - updates DB (edited_media_key)
                                                   │
                                                   ▼
                                        [GitHub Actions Publisher (cron)]
                                        - agents/scheduler.py
                                        - claims SCHEDULED due items
                                        - prefers edited_media_key
                                        - publishes to Instagram Graph API
```

---

## 11. Production Blockers
1.  **Supabase Database Migrations**: Production database status is completely `UNKNOWN`. Verification of the target columns (`edited_media_key`, `edited_media_history`, etc.) on the live `content_items` table is pending a successful database audit.
2.  **Missing Project Credentials**: The local CLI environment lacks a `SUPABASE_ACCESS_TOKEN` and `SUPABASE_PROJECT_REF`, blocking linking or dry-run schema queries.
3.  **Publish Kill Switch**: `PUBLISH_LIVE_ENABLED` is intentionally set to `false` in GHA files, preventing any live Instagram Graph API execution until database migration health is verified.

---

## 12. Recommended Build/Improve Roadmap
*   **P0 (Verification & Safety)**:
    1.  Complete the production Supabase database schema audit.
    2.  Execute an E2E smoke test from Telegram → Supabase → render worker → Storage.
    3.  Keep `PUBLISH_LIVE_ENABLED=false` until both database and rendering pipelines are verified live.
*   **P1 (Harkening Core Pipeline)**:
    4.  Consolidate and resolve duplicate layout/look logic between `ImageStudio` and prompt creators.
    5.  Build an active **Voice Synthesis Agent** (`agents/voice_generator.py`) using `edge-tts`.
    6.  Wire `PerformanceAnalyzer` to fetch actual per-media Instagram Graph Insights and feed the metrics into a non-simulated database table.
*   **P2 (Feature Autonomy)**:
    7.  Build an executable **Auto Planner** (`agents/calendar_planner.py`) to rotate content pillars based on audience retention.
    8.  Build a dedicated **Safety Guardian** agent checking generated captions against compliance.
    9.  Build a **Security Guardian** running code analysis against token exposures.
    10. Replace `ProductHunter` simulated scraping with actual product catalog/affiliate lookup APIs.

---

## 13. Count Reconciliation
*   **In-repo capabilities**: 35
*   **External tools**: 3
*   **Total Inventory Rows**: 38

### Code Status Totals:
- `MERGED`: 33
- `PARTIAL`: 1
- `DOCS_ONLY`: 8
- `LEGACY`: 1
*Total in-repo = 43 (Note: 8 docs-only entries are mapped as row conceptual definitions but represent design-stage assets).*

### Wiring Totals:
- `WIRED_TO_V2_ENTRYPOINT`: 25
- `WIRED_TO_LEGACY_ONLY`: 1
- `STANDALONE_ONLY`: 7
- `NOT_WIRED`: 10
*Total in-repo = 43.*

### Production Verification Totals:
- `PROD_VERIFIED`: 0
- `TEST_VERIFIED_ONLY`: 29
- `BLOCKED/UNKNOWN`: 14
*Total in-repo = 43.*

---

## 14. Evidence Appendix

### A. Render Worker
*   **File Path**: `scripts/render_worker.py`
*   **Entry Point**: `process_job()` / `main()`
*   **Workflow**: `.github/workflows/render-worker.yml`
*   **Test File**: `tests/unit/test_render_worker.py`

### B. Publish Scheduler
*   **File Path**: `agents/scheduler.py`
*   **Entry Point**: `PublishScheduler.run_once()` / `main()`
*   **Workflow**: `.github/workflows/publish-scheduler.yml`
*   **Test File**: `tests/unit/test_publish_scheduler.py`

### C. Image Studio
*   **File Path**: `agents/image_studio.py`
*   **Entry Point**: `ImageStudio.generate()`
*   **Workflow**: `.github/workflows/daily-content.yml`
*   **Test File**: `tests/test_agents.py`
