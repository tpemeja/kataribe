.PHONY: install dev dev-api dev-web check check-api check-web eval eval-api eval-browser fmt

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd backend && uv run uvicorn kataribe.main:app --reload --port 8000

dev-web:
	cd frontend && pnpm dev

check: check-api check-web

check-api:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q

check-web:
	cd frontend && pnpm lint && pnpm test && pnpm build

# Streams real Japanese audio at the Live API. Costs quota and runs in real time.
eval: eval-api eval-browser

eval-api:
	cd backend && uv run pytest -m live -v

eval-browser:
	cd frontend && pnpm test:e2e

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .
