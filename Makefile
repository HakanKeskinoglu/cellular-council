.PHONY: install dev-install test lint format clean build

PYTHON = python3
PIP = $(PYTHON) -m pip
PYTEST = pytest
RUFF = ruff

install:
	$(PIP) install .

dev-install:
	$(PIP) install -e ".[dev]"
	pre-commit install

test:
	$(PYTEST) tests/ -v

test-cov:
	$(PYTEST) tests/ -v --cov=cca --cov-report=term-missing --cov-report=xml

lint:
	$(RUFF) check cca/
	mypy cca/

format:
	$(RUFF) format cca/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov/
	rm -f .coverage
	rm -f coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} +

build:
	$(PIP) install build
	$(PYTHON) -m build
