.DEFAULT_GOAL := help
PYTHON ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: help install run test lint format docker-build docker-up docker-ps docker-logs docker-down tf-fmt tf-validate demo clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Create .venv and install dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements-dev.txt

run: ## Run the API locally with reload (http://127.0.0.1:8000/docs)
	$(BIN)/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test: ## Run the test-suite
	$(BIN)/python -m pytest

lint: ## Lint and format check (no changes)
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Apply formatting and safe lint fixes
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

docker-build: ## Build the image
	docker compose build

docker-up: ## Start API + Prometheus in the background
	docker compose up -d --build

docker-ps: ## Show container status and health
	docker compose ps

docker-logs: ## Follow API logs
	docker compose logs -f cloudrescue

docker-down: ## Stop and remove the containers
	docker compose down

tf-fmt: ## Format Terraform files (local files only)
	terraform -chdir=terraform fmt -recursive

tf-validate: ## Terraform fmt check + init (no backend) + validate. No AWS calls, no apply.
	terraform -chdir=terraform fmt -check -recursive
	terraform -chdir=terraform init -backend=false -input=false
	terraform -chdir=terraform validate

demo: ## Walk through simulate-failure -> recover against a running API
	./scripts/demo.sh

clean: ## Remove caches and the virtualenv
	rm -rf $(VENV) .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
