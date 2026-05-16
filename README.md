# PoiScrapper v3

> Advanced natural-language scraping tool. User cukup ngetik kebutuhan mereka, sistem otomatis cari sumber, scrape lengkap, validasi completeness, lalu kasih hasil siap export.

**Status:** 🏗️ **Phase 0 Foundation** — scaffolding repo + skeleton FE/BE yang bisa ngobrol via `/health`. Flow chat + scraper di Phase 1+. Lihat [`PRD.md`](./PRD.md) untuk spesifikasi lengkap.

---

## Stack

| Area | Teknologi |
|---|---|
| Frontend | Next.js 15 App Router + React 19 + Tailwind CSS v4 + shadcn/ui (new-york) |
| Data fetching | TanStack Query + Zustand untuk local state |
| Backend API | FastAPI + Pydantic v2 + SQLAlchemy 2.0 async (asyncpg) |
| Queue | Celery + Redis |
| Database | PostgreSQL 16 (JSONB) |
| Migrations | Alembic (sync DSN) |
| LLM | Google Gemini 2.0 Flash (free tier) via swappable provider |
| Scraping (Phase 1+) | Playwright + httpx + BeautifulSoup4 |
| Logging | Loguru + stdlib intercept, trace_id per request |
| Tooling | pnpm workspaces + uv + ruff + mypy + eslint + prettier |

Semua tooling **gratis / OSS**. Lihat [`.windsurf/plans/poiscrapper-v3-build-plan-869cf4.md`](./.windsurf/plans/poiscrapper-v3-build-plan-869cf4.md) untuk roadmap 4 fase.

---

## Struktur Repo

```text
v3/
├── apps/
│   ├── api/                 # FastAPI + Celery (satu Python project, dua entry)
│   │   ├── app/
│   │   │   ├── api/         # Route modules (health, …)
│   │   │   ├── core/        # Config, logging, ids
│   │   │   ├── db/          # SQLAlchemy models + session
│   │   │   ├── schemas/     # Pydantic shapes
│   │   │   ├── main.py      # uvicorn entry
│   │   │   └── worker.py    # celery entry
│   │   ├── alembic/         # Migrations
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── web/                 # Next.js 15 App Router
│       ├── src/
│       │   ├── app/         # Pages + layout + providers
│       │   ├── components/  # React components
│       │   └── lib/         # api client, utils, env
│       └── package.json
├── packages/
│   └── shared/              # JSON Schemas + typed TS exports
│       └── schema/          # intent.json, plan.json, record.json, …
├── docker-compose.yml       # Postgres + Redis (profile default) + api/worker (profile app)
├── Makefile                 # Dev tasks
├── pnpm-workspace.yaml
├── package.json             # Root workspace (pnpm)
├── PRD.md
└── README.md
```

---

## Prasyarat

Install tools berikut sebelum mulai:

| Tool | Versi | Keperluan | Link |
|---|---|---|---|
| **Node.js** | ≥ 20 | Frontend + tooling | https://nodejs.org |
| **pnpm** | ≥ 10 | Package manager monorepo | `npm install -g pnpm` |
| **Python** | ≥ 3.12 | Backend + worker | https://www.python.org/downloads/ |
| **uv** | terbaru | Python package manager | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` (Windows) |
| **Docker Desktop** | terbaru | Postgres + Redis lokal | https://www.docker.com/products/docker-desktop |
| **Git** | ≥ 2 | VCS | https://git-scm.com |

> **Windows tip:** pastikan Docker Desktop + WSL2 sudah aktif. `python` di Windows kadang ter-redirect ke Microsoft Store; instal Python resmi dari python.org lalu restart terminal.

---

## Setup Pertama

```bash
# 1. Clone + masuk folder
cd v3

# 2. Install JS deps (monorepo) + approve postinstall scripts Tailwind/sharp
pnpm install
pnpm approve-builds --all    # jawab y untuk @tailwindcss/oxide, sharp, unrs-resolver

# 3. Install Python deps + optional groups
cd apps/api
uv sync --extra dev          # minimum: runtime + dev tooling
# optional (Phase 1+): --extra scraping --extra export
cd ../..

# 4. Copy env + isi (minimal DATABASE_URL* + GEMINI_API_KEY untuk Phase 1)
cp .env.example .env

# 5. Start infra (Postgres + Redis)
docker compose up -d postgres redis

# 6. Jalanin migrasi awal
cd apps/api
uv run alembic upgrade head
cd ../..
```

---

## Menjalankan Dev Env

Buka 3 terminal:

```bash
# Terminal 1 — backend API (FastAPI + hot reload)
cd apps/api
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Celery worker (Phase 0 cuma ping task)
cd apps/api
uv run celery -A app.worker worker --loglevel=info --concurrency=2

# Terminal 3 — frontend (Next.js + Turbopack)
pnpm dev
```

Buka http://localhost:3000 — banner "Backend online" harus hijau. Kalau merah, cek terminal 1 + docker containers (`docker compose ps`).

`/health` di backend return:

```json
{
  "status": "ok",
  "version": "0.0.1",
  "app_env": "development",
  "db":    { "ok": true, "latency_ms": 3.1 },
  "redis": { "ok": true, "latency_ms": 1.4 }
}
```

---

## Tasks Umum (Makefile)

```bash
make help              # daftar target
make infra             # start postgres + redis
make dev-api           # shortcut backend
make dev-worker        # shortcut worker
make dev-web           # shortcut frontend
make migrate           # alembic upgrade head
make migrate-create MSG="add field x"
make db-reset          # nuke + migrate ulang (DATA HILANG)
make lint              # ruff + eslint
make format            # ruff format + prettier
make typecheck         # mypy + tsc --noEmit
make test              # pytest + vitest (Phase 1+)
```

Kalau GNU `make` nggak ada di Windows, semua target ekuivalen ada di `package.json#scripts` atau bisa dijalan manual lewat perintah yang ada di `Makefile`.

---

## Environment Variables (ringkas)

Semua di `.env.example`. Yang **wajib** untuk dev lokal:

```dotenv
DATABASE_URL=postgresql+asyncpg://poiscrapper:poiscrapper_dev@localhost:5432/poiscrapper
DATABASE_URL_SYNC=postgresql+psycopg://poiscrapper:poiscrapper_dev@localhost:5432/poiscrapper
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
GEMINI_API_KEY=                  # dapet dari https://aistudio.google.com/app/apikey (gratis)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Testing

```bash
# Python (FastAPI + services)
cd apps/api
uv run pytest                      # unit + integration
uv run pytest -k smoke             # smoke test saja

# TypeScript (Phase 1+)
pnpm --filter @poi/web test
```

---

## Verifikasi Phase 0 Selesai ✅

- [x] `pnpm install` + `pnpm approve-builds --all` sukses
- [x] `pnpm --filter @poi/web build` sukses (Next.js 15 + Tailwind v4 + React 19 compile)
- [x] `pnpm --filter @poi/web typecheck` hijau
- [x] `pnpm --filter @poi/web lint` hijau (ESLint flat config)
- [x] `pnpm format:check` hijau (Prettier)
- [x] `uv sync --extra dev` di `apps/api` sukses
- [x] `uv run ruff check app` hijau
- [x] `uv run mypy app` hijau (strict, 16 source files)
- [x] `uv run pytest tests` hijau (3/3 smoke tests)
- [x] `docker compose up -d postgres redis` healthy (Postgres 16 + Redis 7)
- [x] `uv run alembic upgrade head` → 7 tables + 6 enums
- [x] `uv run uvicorn app.main:app` → `/health` status `"ok"`
- [x] `uv run celery -A app.worker worker` → `inspect ping` pong + `send_task('ping')` pong
- [x] `pnpm dev` Next.js + buka http://localhost:3000 → banner **"Backend online"** hijau
- [x] Frontend `/api/*` rewrite ke backend (no CORS issue di dev)
- [x] Build plan tersedia: [`@/.windsurf/plans/poiscrapper-v3-build-plan-869cf4.md`](./.windsurf/plans/poiscrapper-v3-build-plan-869cf4.md)

> **Windows gotcha:** `docker` CLI butuh `C:\Program Files\Docker\Docker\resources\bin` di PATH supaya `docker-credential-desktop` ke-resolve. Tambah ke User PATH atau prefix di session: `$env:Path = "C:\Program Files\Docker\Docker\resources\bin;" + $env:Path`.

---

## Next: Phase 1 MVP

Lihat [build plan detail](./.windsurf/plans/poiscrapper-v3-build-plan-869cf4.md) — Phase 1 akan add: chat UI + intent parser Gemini + scraper static/headless + live preview + export CSV.

---

## License

Private — UNLICENSED (MVP internal). Diubah saat rilis publik.
