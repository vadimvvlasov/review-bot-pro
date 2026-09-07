.PHONY: help install backend-install frontend-install dev backend frontend test backend-test frontend-test build lint clean

BACKEND_PORT ?= 8000
BACKEND_DIR := backend
FRONTEND_DIR := frontend

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: backend-install frontend-install ## Install backend + frontend dependencies

backend-install: ## Install backend deps with uv
	cd $(BACKEND_DIR) && uv sync

frontend-install: ## Install frontend deps with npm
	cd $(FRONTEND_DIR) && npm install

dev: ## Run backend + frontend together (Ctrl+C to stop)
	@$(MAKE) -j2 backend frontend

backend: ## Run FastAPI backend with reload (http://localhost:$(BACKEND_PORT))
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --port $(BACKEND_PORT)

frontend: ## Run Vite frontend dev server
	cd $(FRONTEND_DIR) && npm run dev

test: backend-test frontend-test ## Run all tests

backend-test: ## Run backend pytest suite
	cd $(BACKEND_DIR) && uv run pytest -q

frontend-test: ## Run frontend vitest suite
	cd $(FRONTEND_DIR) && npm test

build: ## Build frontend for production
	cd $(FRONTEND_DIR) && npm run build

lint: ## Lint frontend
	cd $(FRONTEND_DIR) && npm run lint

clean: ## Remove build artifacts and caches
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/__pycache__ $(BACKEND_DIR)/app/__pycache__
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.vite
