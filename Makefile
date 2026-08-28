.PHONY: dev dev-logs stop build migrate migrate-create seed test-api lint-api lint-web format help

help:
	@echo "Primo — available commands:"
	@echo "  make dev            Start the full dev stack (api, worker, web, postgres, redis)"
	@echo "  make dev-mock       Same, but with mock providers (no API keys needed)"
	@echo "  make dev-logs       Tail api + worker logs"
	@echo "  make stop           Stop the stack"
	@echo "  make build          Rebuild all images"
	@echo "  make migrate        Apply database migrations"
	@echo "  make migrate-create Create a migration (msg=\"description\")"
	@echo "  make seed           Seed admin user, model registry, and default pricing"
	@echo "  make test-api       Run backend tests"
	@echo "  make lint-api       Lint the backend"
	@echo "  make lint-web       Lint the frontend"
	@echo "  make scan           Scan the working tree for committed secrets"
	@echo "  make format         Format backend + frontend"

dev:
	docker compose -f infrastructure/docker-compose.yml up -d

dev-mock:
	docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.mock.yml up -d

dev-logs:
	docker compose -f infrastructure/docker-compose.yml logs -f api worker

stop:
	docker compose -f infrastructure/docker-compose.yml down

build:
	docker compose -f infrastructure/docker-compose.yml build

migrate:
	docker compose -f infrastructure/docker-compose.yml exec api alembic upgrade head

migrate-create:
	docker compose -f infrastructure/docker-compose.yml exec api alembic revision --autogenerate -m "$(msg)"

seed:
	docker compose -f infrastructure/docker-compose.yml exec api python -m app.scripts.seed

test-api:
	docker compose -f infrastructure/docker-compose.yml exec api pytest -v

lint-api:
	docker compose -f infrastructure/docker-compose.yml exec api ruff check .

lint-web:
	cd apps/web && npm run lint

scan:
	python infrastructure/scripts/secret_scan.py

format:
	docker compose -f infrastructure/docker-compose.yml exec api ruff format .
	cd apps/web && npm run format
