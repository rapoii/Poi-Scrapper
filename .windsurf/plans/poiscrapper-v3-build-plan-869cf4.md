# PoiScrapper v3 — Build Plan

> Phased delivery plan dari scaffolding sampai production-ready scraping platform.
> Mengacu ke `@/PRD.md` untuk product spec.

---

## Strategi: Phased Delivery (MVP → v1 → v2)

Kita pecah jadi **4 fase** supaya tiap fase punya milestone yang demo-able dan ngga kunjung selesai. Tiap fase dibangun di atas yang sebelumnya.

| Fase | Nama | Goal | Demo-able output |
|---|---|---|---|
| 0 | Foundation | Repo + infra + skeleton FE/BE bisa ngobrol | Frontend banner: "Backend online · db ok · redis ok" |
| 1 | MVP | End-to-end happy path satu prompt → satu tabel → CSV | Ketik *"data dokter di RS Siloam Karawaci"* → preview tabel → download CSV |
| 2 | Production-Ready | Auth, multi-user, monitoring, lebih banyak strategy | Login Google, schedule run manual, audit log per job |
| 3 | Advanced | Recurring, browser extension, domain packs | Schedule cron, change detection, marketplace template |

---

## Phase 0 — Foundation

**Status:** ✅ COMPLETE.

### Deliverables

- [x] **Monorepo scaffold** — pnpm workspace, `apps/` + `packages/` + root config
  - `@/package.json` (workspace root)
  - `@/pnpm-workspace.yaml` + `@/.npmrc` + `@/.gitignore` + `@/.editorconfig`
  - `@/.prettierrc.json` + `@/.prettierignore`
- [x] **Infra** — Postgres 16 + Redis 7 via Docker Compose
  - `@/docker-compose.yml`
  - Healthcheck untuk kedua container
- [x] **Shared package** — JSON Schema master + TS types codegen
  - `@/packages/shared/schema/` (intent, source, plan, record, job, ws_event)
  - `@/packages/shared/scripts/codegen.mjs` (json-schema → TS)
  - `@/packages/shared/src/index.ts` (typed exports)
  - Build output `dist/index.js` + `dist/index.d.ts` ✅ verified
- [x] **Backend skeleton** — FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic
  - `@/apps/api/pyproject.toml` (deps + ruff + mypy + pytest config)
  - `@/apps/api/app/main.py` (lifespan + CORS + trace_id middleware + global error handler)
  - `@/apps/api/app/core/config.py` (Pydantic Settings)
  - `@/apps/api/app/core/logging.py` (Loguru + stdlib intercept + trace_id ctxvar)
  - `@/apps/api/app/db/base.py` + `models.py` + `session.py`
  - `@/apps/api/app/api/health.py` (`/health` + `/version`)
  - `@/apps/api/Dockerfile`
- [x] **Migrasi awal** — Alembic dengan 6 tables + 6 enums per PRD §6
  - `@/apps/api/alembic.ini` + `@/apps/api/alembic/env.py`
  - `@/apps/api/alembic/versions/20260509_0000_initial_schema.py`
  - Verified: `alembic upgrade head` → 7 tables (incl. alembic_version) + 6 enums in DB
- [x] **Worker skeleton** — Celery + ping task
  - `@/apps/api/app/worker.py`
  - Verified: `celery inspect ping` → `pong`, `send_task('ping')` → `pong`
- [x] **Frontend skeleton** — Next.js 15 + React 19 + Tailwind v4 + shadcn-ready
  - `@/apps/web/next.config.ts` (rewrite `/api/*` → backend, no CORS)
  - `@/apps/web/src/app/layout.tsx` (Inter + JetBrains Mono fonts)
  - `@/apps/web/src/app/page.tsx` (landing Phase 0)
  - `@/apps/web/src/components/health-banner.tsx` (TanStack Query polling `/health`)
  - `@/apps/web/src/lib/api.ts` (typed fetch client, relative URL)
  - `@/apps/web/src/app/globals.css` (OKLCH design tokens, light + dark)
  - `@/apps/web/components.json` (shadcn config new-york)
  - Build verified: `next build` ✅
- [x] **Tooling** — ESLint flat config, Ruff, Mypy strict, Prettier, pre-commit hooks (TBD)
  - ESLint: clean (after fix flat config global ignores)
  - Ruff: clean (B008 ignored = FastAPI `Depends` pattern)
  - Mypy strict: clean (16 source files)
  - Prettier: clean
- [x] **VS Code setup** — settings + extension recommendations + Tailwind v4 CSS data
  - `@/.vscode/settings.json`
  - `@/.vscode/extensions.json`
  - `@/.vscode/tailwind-v4.css-data.json`
- [x] **Makefile** — dev tasks (infra, dev-api, dev-worker, dev-web, migrate, lint, format, typecheck, test, clean)
- [x] **Documentation** — Root README + per-package READMEs
  - `@/README.md`
  - `@/apps/api/README.md`
  - `@/apps/web/README.md` (Next.js default)
  - `@/packages/shared/README.md`
- [x] **Smoke tests** — pytest 3 tests passing (import, config, version endpoint)

### Phase 0 verification (E2E)

```text
✅ pnpm install + approve-builds
✅ docker compose up -d postgres redis (both healthy)
✅ uv sync --extra dev
✅ alembic upgrade head (7 tables + 6 enums)
✅ uv run uvicorn app.main:app --reload (API on :8000)
✅ uv run celery -A app.worker worker (broker → pong)
✅ pnpm dev (Next on :3000)
✅ Browser → :3000 → banner "Backend online · db ok · redis ok" (HIJAU)
✅ All quality gates: ruff, mypy, eslint, prettier, pytest
```

---

## Phase 1 — MVP (Happy Path E2E)

**Status:** 🚧 IN PROGRESS.

**Last updated:** 2026-05-14.

Progress terbaru:

- [x] Phase 1.1 Chat UI + preview shell.
- [x] Phase 1.2 Intent Parser LLM chain + cache + fallback circuit breaker.
- [x] Phase 1.2b editable plan intent: backend PATCH + FE Plan Editor.
- [x] Phase 1.3a source discovery MVP: synchronous backend endpoint, DB persistence, plan update, FE discover button + source list.
- [x] Phase 1.3b async Celery discovery + WebSocket progress.
- [x] Phase 1.4a source checklist + approve/run action.
- [x] Phase 1.4b edit prompt + re-parse flow.
- [x] Phase 1.5a scraper worker MVP: static fetch, heuristic extraction, records insert, run/source/job status updates.
- [x] Phase 1.5b adaptive strategy upgrades: LLM multi-record extraction, robots.txt enforcement + override warning, headless fallback, max concurrency 3.
- [x] Phase 1.6a records API + live preview table.
- [x] Phase 1.6b live preview polish: TanStack Table resize, virtualized rows, in-memory cell edit, SourceProgressBadge detail.
- [x] Phase 1.7 Export CSV: backend CSV stream + export audit row + FE download button.
- [x] Phase 1.8 Job History: frontend sidebar lists jobs and reloads previous job previews.

**Goal:** Satu prompt natural-language → preview tabel data → export CSV. Single-user lokal, no auth.

### Scope

#### 1.1 Chat UI (FE) — ✅ COMPLETE
- `@/apps/web/src/app/(chat)/page.tsx` — main chat layout (split: chat panel + preview panel)
- Chat input (multiline textarea + send button + keyboard shortcut)
- Message bubbles (user prompt + system plan + system progress)
- shadcn/ui components: `Button`, `Textarea`, `Card`, `ScrollArea`, `Avatar`
- Welcome state ("Coba: data dokter di RS Siloam Karawaci")
- Empty state per panel kanan

#### 1.2 Intent Parser (BE) — ✅ COMPLETE
- `@/apps/api/app/services/llm/` — provider abstraction (Gemini default, Groq + OpenRouter fallback)
  - `base.py` — `LLMProvider` protocol
  - `gemini.py` — `google-genai` SDK call
  - `factory.py` — pilih provider by `LLM_PROVIDER` env
- `@/apps/api/app/services/intent_parser.py` — turn prompt → `Intent` (entity, fields, filters, scope)
- Output JSON Schema-validated against `@/packages/shared/schema/intent.json`
- POST `/jobs` endpoint: terima prompt, panggil intent parser, simpan ke `jobs` table dengan status `draft`
- Few-shot prompt template untuk infer field per entity (dokter, RS, restoran, dll)

#### 1.3 Source Discovery (BE) — ✅ COMPLETE
- `@/apps/api/app/services/source_discovery.py`
- Strategi: pakai LLM untuk suggest URL kandidat berdasarkan intent (alternatif: Tavily API gratis tier)
- Output `Source[]` dengan `reliability_score` (manual heuristic: domain authority approx + field coverage)
- Insert ke `sources` table dengan status `pending`
- Endpoint `POST /jobs/{id}/discover` → trigger Celery task → push status via WebSocket

Status implementasi:

- [x] `source_discovery.py` dengan LLM-backed planner + heuristic fallback offline.
- [x] `POST /jobs/{id}/discover` sinkron untuk Phase 1.3a; idempotent, persist ke tabel `sources`, dan update `jobs.parsed_plan.sources`.
- [x] Frontend tombol Discover/Refresh + daftar source kandidat di preview panel.
- [x] Tests backend untuk source discovery endpoint + idempotency.
- [x] Ubah discovery menjadi Celery task async dan push progress via WebSocket:
  - `POST /jobs/{id}/discover` default enqueue `jobs.discover_sources`; `?async=false` tetap tersedia untuk smoke/integration test.
  - Worker publish `progress` / `done` / `error` ke Redis Pub/Sub.
  - WebSocket `/ws/jobs/{id}` subscribe event per job; FE refresh plan saat `done`.

#### 1.4 Plan Confirmation (FE) — ✅ COMPLETE
- Komponen `PlanCard` — tampilin entity + fields + sources (checklist editable)
- User bisa: edit fields (add/remove), uncheck sources, edit prompt + re-parse
- Approve → POST `/jobs/{id}/run`

Status implementasi:

- [x] Source checklist editable di preview panel; source disimpan sebagai `pending` / `skipped`.
- [x] `PATCH /jobs/{id}/sources` untuk persist pilihan user + `override_robots`.
- [x] `POST /jobs/{id}/run` validasi minimal 1 source, buat `runs` row, set job ke `running`, dan publish `job_status` event.
- [x] Frontend tombol Approve & Run + optimistic refresh via TanStack Query.
- [x] Tests backend untuk skip/reenable source, cross-job source rejection, dan run validation.
- [x] Edit prompt + re-parse dari UI chat:
  - `POST /jobs/{id}/reparse` mengganti prompt + parsed plan dan menghapus source kandidat lama.
  - Saat job masih `planning`, input chat menjadi revisi plan aktif; setelah job `running`, input kembali membuat job baru.
  - Tests backend untuk re-parse + source reset dan reject re-parse pada job running.

#### 1.5 Adaptive Scraper (BE Worker) — ✅ COMPLETE
- `@/apps/api/app/services/scraper/` — strategy pattern
  - `base.py` — `ScraperStrategy` protocol
  - `static_html.py` — httpx + best-effort text extraction (default, fastest)
  - `headless.py` — Playwright (JS-rendered fallback)
  - `dispatcher.py` — pilih strategy auto (sniff content-type + JS heuristic)
- Per source: fetch → parse → LLM extract structured fields → insert `records`
- Respect `robots.txt` (lib `protego`) + warning override
- Concurrency: Celery group, max 3 sources parallel
- Update `runs` table per source progress

Status implementasi:

- [x] `app/services/scraper/` scaffold: `base.py`, `static_html.py`, `dispatcher.py`, `runner.py`.
- [x] `jobs.run_scrape` Celery task; `POST /jobs/{id}/run` enqueue task by default and supports `?async=false` for smoke/integration tests.
- [x] Static HTML scraper with httpx fetch + heuristic one-record extraction into requested fields.
- [x] Insert `records`, update `sources`, `runs`, and `jobs` aggregates/status (`done`/`partial`/`failed`).
- [x] Publish `source_status`, `record_upsert`, `progress`, and `done` events over existing Redis/WebSocket bus.
- [x] Tests for synchronous scrape path inserting records and aggregate scores.
- [x] LLM-assisted multi-record extraction per source.
- [x] Robots.txt enforcement + override warning path.
- [x] Headless Playwright fallback and static HTML app-shell sniffing.
- [x] Parallel source scraping with max concurrency 3.

#### 1.6 Live Preview (FE) — ✅ COMPLETE
- WebSocket `/ws/jobs/{id}` — push event `record.added` | `source.completed` | `job.done`
- `RecordsTable` (TanStack Table) — virtual scroll, column resize, cell edit (in-memory)
- `CompletenessChip` per row (warna based on score 0–1)
- `SourceProgressBadge` per source (pending / running / done / failed)

Status implementasi:

- [x] `GET /jobs/{id}/records` untuk list record hasil scrape, dengan pagination simple.
- [x] Frontend `RecordsPreview` menampilkan tabel dinamis dari `intent.required_fields`.
- [x] Tabel records refetch saat WebSocket menerima `record_upsert` atau scrape `done`.
- [x] Completeness badge per row dan source URL link.
- [x] Tests backend untuk records endpoint + 404.
- [x] TanStack Table virtual scroll/resize.
- [x] Cell edit in-memory.
- [x] SourceProgressBadge detail per source.

#### 1.7 Export CSV (BE + FE) — ✅ COMPLETE
- `@/apps/api/app/services/export/csv.py` — stream CSV from records
- Endpoint `GET /jobs/{id}/export?format=csv` → `text/csv`
- FE: button "Export CSV" → trigger download
- Insert row ke `exports` table

Status implementasi:

- [x] CSV column order follows `intent.required_fields`, then extra record keys, then metadata (`source_url`, `completeness_score`, `confidence_score`, `scraped_at`).
- [x] Endpoint returns downloadable CSV with deterministic filename and rejects empty jobs with `409`.
- [x] Export requests insert an `exports` audit row with columns, byte size, and row count.
- [x] Frontend Records preview has an Export CSV action that downloads via blob.
- [x] Tests cover CSV content, export persistence, empty job, and unknown job.

#### 1.8 Job History — ✅ COMPLETE
- `GET /jobs` — list user's jobs (untuk Phase 1 single-user, no filter user_id)
- Sidebar di FE: list semua job sebelumnya, click untuk re-load preview

Status implementasi:

- [x] `JobHistorySidebar` lists recent jobs via existing `GET /jobs`.
- [x] Selecting a job fetches full detail and restores chat + preview state.
- [x] New job action clears the active job and returns the chat to the welcome state.
- [x] Sidebar refresh action and query invalidation keep history in sync after job updates.

### Phase 1 acceptance test

> User ketik *"data dokter spesialis jantung di RS Siloam Karawaci"*
> 1. Plan muncul dalam ≤ 5 detik (entity: dokter, fields: nama/spesialisasi/jadwal/STR/poli/...)
> 2. User klik Approve
> 3. Tabel preview update real-time, ≥ 5 record terisi dalam ≤ 30 detik
> 4. Completeness rata-rata ≥ 0.6
> 5. Export CSV → file downloadable + valid CSV

---

## Phase 2 — Production-Ready

**Status:** 📋 PLANNED.

**Goal:** Multi-user dengan auth, observability, lebih banyak format export, audit trail.

### Scope

- **Auth** — Supabase Auth (email/password + Google OAuth). RLS di Postgres untuk isolasi user data.
- **Multi-user** — semua endpoints butuh `user_id` di context. Rate limit per user (`slowapi`).
- **Re-run** — incremental scrape, simpan diff di `runs.diff` (records added/updated/removed).
- **More formats** — XLSX (`openpyxl` streaming) + JSON (line-delimited).
- **Notifications** — email on done/fail (Resend). In-app toast (sonner sudah ada).
- **Observability** — Sentry SDK + OpenTelemetry traces (Jaeger/Grafana Tempo). Metrics di Prometheus format.
- **Object storage** — Cloudflare R2 (S3-compat) untuk export files (signed URL, expire 7 hari).
- **PII detection** — heuristic + optional LLM scan; warning modal sebelum export kalau ada PII.
- **Job pause/cancel** — Celery revoke task + persist state.

### Phase 2 acceptance test

> 1. User register via Google, login, lihat job pribadi (gak ke-leak ke user lain).
> 2. Run job → email notif saat done.
> 3. Re-run job → diff tampil di UI (3 added, 1 updated, 0 removed).
> 4. Export XLSX → file di R2 dengan signed URL, valid 7 hari.
> 5. Sentry capture error + tampilin trace_id.

---

## Phase 3 — Advanced

**Status:** 📋 PLANNED.

**Goal:** Recurring jobs, advanced strategy, ekosistem ekstensi.

### Scope

- **Scheduled runs** — Celery beat (cron-style), per job punya `schedule` field optional.
- **Change detection** — alert email kalau data berubah > threshold per run.
- **Domain packs** — preset bundle field + validator per vertical (Medical, Real Estate, F&B, E-commerce).
- **Browser extension** — capture page → kirim sebagai seed source ke job.
- **Public API** — REST + webhook untuk Zapier / n8n integration.
- **Proxy rotation** — Bright Data / Smartproxy plugin, smart fallback by site.
- **CAPTCHA solver** — 2Captcha plugin, opsional per site.
- **Marketplace prompt** — komunitas share prompt template (read-only Phase 3, write Phase 4).

---

## Cross-cutting concerns (di semua fase)

1. **Type-safety end-to-end** — JSON Schema master di `packages/shared/schema/*` jadi single source of truth → di-codegen ke TS + Python (Pydantic) untuk konsistensi.
2. **Trace ID propagation** — setiap request HTTP + WebSocket + Celery task carry `trace_id` via header/contextvar untuk debugging end-to-end.
3. **Cost control** — LLM call selalu cache by prompt hash (Phase 1+); token budget per job (default $0.50).
4. **Test pyramid** — unit (services), integration (DB + worker), e2e (Playwright untuk FE flow Phase 1+).

---

## Tech Stack rasionale (singkat)

| Layer | Pilihan | Kenapa |
|---|---|---|
| Frontend framework | **Next.js 15 + React 19** | App Router + Server Components matang; Turbopack dev fast; ekosistem besar |
| Styling | **Tailwind CSS v4 + shadcn/ui** | OKLCH support, design token native, copy-paste komponen high-quality |
| Data fetching | **TanStack Query + Zustand** | Server state vs client state separation; SWR alt rejected karena Query fitur lebih lengkap |
| API framework | **FastAPI** | Async-native, Pydantic v2, OpenAPI auto-gen, type hints first-class |
| ORM | **SQLAlchemy 2.0 async** | Industry-standard Python ORM; asyncpg driver fastest |
| Migrations | **Alembic** (sync DSN) | Standard SQLAlchemy partner; sync DSN simpler, no async issues di migration runner |
| Queue | **Celery + Redis** | Battle-tested; Celery Beat untuk Phase 3 scheduling. Alternatif Dramatiq/RQ rejected: Celery features superset. |
| LLM (default) | **Gemini 2.0 Flash** | Free tier generous (1500 req/day), latency rendah, JSON mode reliable |
| LLM fallback | **Groq + OpenRouter** | Speed (Groq) + model variety (OpenRouter routing) |
| Scraping | **Playwright + httpx + selectolax** | Playwright untuk JS-rendered, httpx + selectolax untuk static (10× faster than BeautifulSoup) |
| Logging | **Loguru** | Structured + colorize + intercept stdlib di satu place |
| Observability (Phase 3) | **Sentry + OpenTelemetry** | Sentry untuk errors, OTLP untuk traces/metrics |
| Storage (Phase 2) | **Cloudflare R2** | S3-compatible, no egress fees |
| Auth (Phase 2) | **Supabase Auth** | Free tier OK, RLS bawaan, social provider support |

Semua tools diatas **gratis / OSS / free tier**.
