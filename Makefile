# InnerBoard-local Makefile

.PHONY: help install install-dev test test-cov test-no-network lint format clean docker-build docker-run docker-stop setup-ollama

# Determine docker compose command (supports v2 plugin and legacy v1)
ifeq ($(shell command -v docker-compose >/dev/null 2>&1; echo $$?),0)
DOCKER_COMPOSE := docker-compose
else ifeq ($(shell command -v docker >/dev/null 2>&1; echo $$?),0)
DOCKER_COMPOSE := docker compose
else
DOCKER_COMPOSE := docker-compose
endif

# Default target
help: ## Show this help message
	@echo "InnerBoard-local Commands:"
	@echo "Installation & Setup:"
	@grep -E '^(install|setup|health|docker-setup):.*## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Development:"
	@grep -E '^(test|lint|format|ci):.*## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Docker:"
	@grep -E '^(docker-):.*## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install InnerBoard-local
	pip install -e .

install-dev: ## Install with development dependencies
	pip install -e ".[dev]"

# Testing
test: ## Run all tests
	pytest tests/ -v

test-cov: ## Run tests with coverage
	pytest tests/ --cov=app --cov-report=html --cov-report=term

test-no-network: ## Run network safety tests
	pytest tests/test_no_network.py -v

# Code Quality
lint: ## Run linting checks
	flake8 app/ tests/
	mypy app/

format: ## Format code with black
	black app/ tests/

# Docker
docker-build: ## Build Docker image
	docker build -t innerboard-local .

docker-run: ## Run InnerBoard in Docker
	docker run --rm -it \
		--network host \
		-v $(PWD)/data:/app/data \
		innerboard-local

docker-compose-up: ## Start all services with docker-compose
	$(DOCKER_COMPOSE) up -d

docker-compose-down: ## Stop all services
	$(DOCKER_COMPOSE) down

# Setup commands
setup: ## Complete setup (install + ollama + vault)
	@echo "🚀 Running complete InnerBoard setup..."
	$(MAKE) install
	$(MAKE) setup-ollama
	innerboard init --no-interactive
	innerboard health

setup-interactive: ## Interactive setup wizard
	@echo "🚀 Running interactive setup..."
	innerboard setup

setup-ollama: ## Setup Ollama and pull default model
	@echo "🤖 Setting up Ollama..."
	@if command -v ollama >/dev/null 2>&1; then \
		echo "Ollama already installed"; \
	else \
		echo "Installing Ollama..."; \
		if [[ "$$OSTYPE" == "darwin"* ]]; then \
			if command -v brew >/dev/null 2>&1; then \
				brew install ollama; \
			else \
				echo "Please install Homebrew first: https://brew.sh/"; \
				exit 1; \
			fi \
		else \
			curl -fsSL https://ollama.com/install.sh | sh; \
		fi \
	fi
	@echo "Starting Ollama service..."
	@if [[ "$$OSTYPE" == "darwin"* ]]; then \
		brew services start ollama 2>/dev/null || ollama serve & \
	else \
		ollama serve & \
	fi
	@sleep 3
	@echo "Pulling default model (gpt-oss:20b)..."
	ollama pull gpt-oss:20b

health: ## Run health checks
	@echo "🔍 Running health checks..."
	innerboard health --detailed

docker-setup: ## Setup with Docker
	@echo "🐳 Setting up with Docker..."
	./docker-setup.sh

# Development setup
dev-setup: install-dev setup-ollama ## Set up development environment

# Cleaning
clean: ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/
	rm -rf dist/ build/

clean-all: clean ## Clean everything including data
	rm -f vault.db vault.key
	rm -rf data/

# Quick demo
demo: ## Run a quick demo
	@echo "Adding a demo reflection..."
	python -m app.main add --text "I'm struggling with the Kubernetes ingress setup. The documentation seems outdated and I can't get the routing to work properly."

# CI/CD simulation
ci: lint test-cov ## Run CI checks

# Production deployment
deploy-docker: docker-build ## Build and deploy with Docker
	docker tag innerboard-local innerboard-local:latest
	@echo "Docker image built. Run with: make docker-run"

# Help for environment variables
env-help: ## Show available environment variables
	@echo "Available Environment Variables:"
	@echo "  OLLAMA_MODEL     - Model to use (default: gpt-oss:20b)"
	@echo "  OLLAMA_HOST      - Ollama server host (default: http://localhost:11434)"
	@echo "  OLLAMA_TIMEOUT   - Request timeout in seconds (default: 30)"
	@echo "  MAX_TOKENS       - Maximum tokens to generate (default: 100000)"
	@echo "  MODEL_TEMPERATURE- Sampling temperature (default: 0.7)"
	@echo "  MODEL_TOP_P      - Top-p sampling (default: 0.95)"
	@echo "  LOG_LEVEL        - Logging level (default: ERROR)"
	@echo "  LOG_FILE         - Log file path (optional)"
	@echo "  INNERBOARD_DB_PATH - Database file path (default: vault.db)"
	@echo "  INNERBOARD_KEY_PATH - Key file path (default: vault.key)"
	@echo "  ALLOW_LOOPBACK   - Allow loopback connections (default: true)"
	@echo "  ALLOWED_PORTS    - Comma-separated allowed ports (default: 11434)"
	@echo "  ENABLE_CACHING   - Enable response caching (default: true)"
	@echo "  CACHE_TTL_SECONDS- Cache TTL in seconds (default: 3600)"
