.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

UV ?= uv
VENV ?= .venv
PY := $(VENV)/bin/python
COVERAGE_MIN ?= 70

.PHONY: help venv bootstrap install dev-install lint type-check coverage check test test-lf build clean release

ifeq ($(filter release,$(MAKECMDGOALS)),release)
ifndef VERSION
$(error VERSION is required (e.g. make release VERSION=1.2.3))
endif
endif

## Show this help message
help:
	@awk '\
	  BEGIN {FS = ":"} \
	  /^### / {section=substr($$0,5); next} \
	  /^##/ {sub(/^## ?/, "", $$0); helpMsg = $$0; next} \
	  /^[a-zA-Z0-9_.-]+:/ { \
	    sub(/:.*/, "", $$1); \
	    if (helpMsg) { \
	      if (section) { \
	        printf "\n\033[1m%s\033[0m\n", section; \
	        section = ""; \
	      } \
	      printf "  \033[36m%-20s\033[0m %s\n", $$1, helpMsg; \
	      helpMsg = ""; \
	    } \
	  }' $(MAKEFILE_LIST)

### Setup
## Create local virtual environment if missing
venv:
	@test -d $(VENV) || python3 -m venv $(VENV)

## Upgrade pip tooling in .venv
bootstrap: venv
	$(PY) -m pip install --upgrade pip

## Install runtime dependencies in .venv
install:
	$(UV) sync

## Install dev dependencies in .venv
dev-install:
	$(UV) sync --extra dev

### Quality
## Run pre-commit hooks on all files
lint: dev-install
	$(UV) run pre-commit run --all-files

## Run static type checks
type-check: dev-install
	$(UV) run mypy src/ tests/

## Run coverage report with fail-under threshold
coverage: dev-install
	$(UV) run pytest --cov=src/djvrt --cov-report=term-missing --cov-report=xml --cov-fail-under=$(COVERAGE_MIN)

## Run all quality checks (lint + type checking + coverage + build)
check: lint type-check coverage build

## Run test suite
test: dev-install
	$(UV) run pytest

## Re-run last failed tests
test-lf: dev-install
	$(UV) run pytest --lf -x

### Build & Release
## Build package artifacts and validate metadata
build: dev-install
	$(UV) build
	$(UV) run twine check dist/*

## Remove local build/test artifacts
clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov
	find src tests -type d -name "__pycache__" -exec rm -rf {} +
	find src tests -type d -name "*.egg-info" -exec rm -rf {} +

## Build release artifacts and print tag instructions
release: check
	@echo "Release ready."
	@echo "Next: tag and push to trigger PyPI release:"
	@echo "  git tag v$(VERSION)"
	@echo "  git push origin v$(VERSION)"
	@echo "See .github/workflows/publish.yml for automatic release pipeline."
