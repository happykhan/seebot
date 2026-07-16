.PHONY: install test lint typecheck schemas web check gate

install:
	uv sync --all-extras
	cd web && npm ci

test:
	uv run pytest --cov=seebot --cov-report=term-missing

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy src

schemas:
	uv run seebot manifest validate-all
	uv run seebot fixture validate

web:
	cd web && npm test && npm run build && npm run test:visual

check: lint typecheck test schemas web

gate:
	./scripts/run_cohort.sh --dry-run
