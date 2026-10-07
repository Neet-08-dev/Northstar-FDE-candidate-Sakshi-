UV ?= $(shell command -v uv 2>/dev/null || echo .tools/uv/bin/uv)
.DEFAULT_GOAL := help
.PHONY: help setup check dev eval-offline eval-live public-evals
help:
	@echo 'setup: locked dependencies | check: offline lint/types/tests | dev: local demo'
	@echo 'eval-offline: authored deterministic scenarios | eval-live: paid model scenarios'
	@echo 'public-evals: published scenarios against running local services'
setup:
	sh scripts/setup.sh
check:
	$(UV) run --frozen ruff check .
	$(UV) run --frozen ruff format --check .
	$(UV) run --frozen mypy
	$(UV) run --frozen python -m unittest discover -s tests -v
dev:
	$(UV) run --frozen python -m starter.dev
eval-offline:
	$(UV) run --frozen python -m evals.run --offline
eval-live:
	$(UV) run --frozen python -m evals.run --trials 1
public-evals:
	$(UV) run --frozen python -m public.run
