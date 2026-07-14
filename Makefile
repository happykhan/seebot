.PHONY: install test lint typecheck schemas web check pilot

install:
	uv sync --all-extras
	cd web && npm ci

test:
	uv run pytest --cov=bioconda_audit --cov-report=term-missing

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy src

schemas:
	uv run bcqa manifest validate-all

web:
	cd web && npm run build

check: lint typecheck test schemas web

pilot:
	./scripts/run_pilot.sh

