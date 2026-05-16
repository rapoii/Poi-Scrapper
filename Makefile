# PoiScrapper v3 — dev tasks
# Usage (Windows pwsh): `make <target>` (butuh GNU Make atau pakai `pnpm run` setara)
# Kalau tidak punya make, semua target di bawah punya padanan di scripts package.json
# atau bisa dijalankan manual sesuai komennya.

.PHONY: help infra infra-down dev dev-api dev-worker dev-web install install-py install-js \
        migrate migrate-create db-reset lint format test typecheck clean

help: ## Tampilkan daftar target
	@echo "PoiScrapper v3 - Available make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------- Infrastructure ----------
infra: ## Start postgres + redis via docker compose
	docker compose up -d postgres redis

infra-down: ## Stop infra containers (data tetap)
	docker compose down

infra-nuke: ## Stop infra + hapus volume (DATA HILANG)
	docker compose down -v

# ---------- Install ----------
install: install-js install-py ## Install semua dependency (JS + Python)

install-js: ## Install JS dependency (pnpm workspace)
	pnpm install

install-py: ## Install Python dependency (uv sync, jalan di apps/api)
	cd apps/api && uv sync

# ---------- Dev servers ----------
dev-api: ## Start FastAPI dev server (reload on change)
	cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Start Celery worker
	cd apps/api && uv run celery -A app.worker worker --loglevel=info --concurrency=2

dev-web: ## Start Next.js dev server (turbopack)
	pnpm --filter @poi/web dev

dev: infra ## Short-hand: pastikan infra jalan (FE/BE jalan manual di terminal terpisah)
	@echo ""
	@echo "Infra siap. Jalankan di terminal terpisah:"
	@echo "  make dev-api"
	@echo "  make dev-worker"
	@echo "  make dev-web"

# ---------- Database ----------
migrate: ## Jalanin alembic upgrade head
	cd apps/api && uv run alembic upgrade head

migrate-create: ## Generate migrasi baru dari autogenerate (pakai MSG=...)
	cd apps/api && uv run alembic revision --autogenerate -m "$(MSG)"

db-reset: infra-nuke infra migrate ## Reset full DB + migrasi fresh (data hilang!)

# ---------- Quality ----------
lint: ## Lint JS + Python
	pnpm -r --if-present lint
	cd apps/api && uv run ruff check .

format: ## Format JS + Python
	pnpm format
	cd apps/api && uv run ruff format .

typecheck: ## Typecheck JS + Python
	pnpm -r --if-present typecheck
	cd apps/api && uv run mypy app

test: ## Test JS + Python
	pnpm -r --if-present test
	cd apps/api && uv run pytest

# ---------- Clean ----------
clean: ## Hapus semua artefak build
	pnpm clean
	cd apps/api && rm -rf .venv .mypy_cache .ruff_cache .pytest_cache htmlcov
