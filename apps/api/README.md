# apps/api — PoiScrapper v3 Backend

FastAPI orchestrator + Celery scraper worker. Satu Python project, dua entry point.

## Prasyarat

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) untuk dependency management
- Postgres + Redis jalan (lewat `docker compose up -d postgres redis` dari root)

## Setup

```bash
cd apps/api
uv sync            # install semua deps + optional groups
uv sync --extra scraping --extra export --extra dev
```

## Menjalankan

```bash
# API (hot reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker
uv run celery -A app.worker worker --loglevel=info --concurrency=2
```

## Migrasi

```bash
uv run alembic upgrade head                      # apply
uv run alembic revision --autogenerate -m "msg"  # generate
uv run alembic downgrade -1                      # rollback 1 step
```

## Struktur

```
app/
  main.py            # FastAPI entry
  worker.py          # Celery entry (share codebase)
  api/               # Route modules
  core/              # Config, logging, ids, constants
  db/                # Models + session factory
  schemas/           # Pydantic schemas (API contracts)
  services/          # Business logic (intent, discovery, scraper, validator)
alembic/
  env.py             # Alembic config (pakai sync engine utk migrasi)
  versions/          # Migration scripts
tests/
```
