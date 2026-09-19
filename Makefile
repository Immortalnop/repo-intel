.PHONY: install lint format type test cov all serve

install:
	pip install -e ".[dev]"

lint:
	ruff check repo_intel tests

format:
	black repo_intel tests

type:
	mypy repo_intel

test:
	pytest

cov:
	pytest --cov=repo_intel --cov-report=term-missing --cov-fail-under=85

all: lint format type cov

serve:
	repo-intel serve .
