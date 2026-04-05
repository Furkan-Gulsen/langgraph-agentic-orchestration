PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install run lint typecheck

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"

run:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

lint:
	$(VENV)/bin/ruff check app

typecheck:
	$(VENV)/bin/mypy app
