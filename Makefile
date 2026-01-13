.PHONY: up down logs test clean build shell lint

# Default target
.DEFAULT_GOAL := help

# Help target
help:
	@echo "Lyftr Webhook API - Available commands:"
	@echo ""
	@echo "  make up       - Start the application (docker compose up -d --build)"
	@echo "  make down     - Stop and remove containers (docker compose down -v)"
	@echo "  make logs     - View application logs (docker compose logs -f api)"
	@echo "  make test     - Run tests"
	@echo "  make build    - Build the Docker image"
	@echo "  make clean    - Clean up Docker resources"
	@echo "  make shell    - Open a shell in the running container"
	@echo "  make lint     - Run linting checks"
	@echo ""

# Start the application
up:
	docker compose up -d --build

# Stop the application and remove volumes
down:
	docker compose down -v

# View logs
logs:
	docker compose logs -f api

# Run tests
test:
	@echo "Running tests..."
	@if [ -f requirements.txt ]; then \
		pip install -q -r requirements.txt; \
	fi
	WEBHOOK_SECRET=testsecret DATABASE_URL=sqlite:///test.db pytest tests/ -v --tb=short
	@rm -f test.db

# Build Docker image only
build:
	docker compose build

# Clean up Docker resources
clean:
	docker compose down -v --rmi local
	docker system prune -f

# Open shell in container
shell:
	docker compose exec api /bin/sh

# Run linting (requires flake8 and black installed locally)
lint:
	@echo "Running linting checks..."
	@if command -v flake8 > /dev/null; then \
		flake8 app/ tests/ --max-line-length=100; \
	else \
		echo "flake8 not installed, skipping..."; \
	fi
	@if command -v black > /dev/null; then \
		black --check app/ tests/; \
	else \
		echo "black not installed, skipping..."; \
	fi

# Local development server (without Docker)
dev:
	WEBHOOK_SECRET=testsecret DATABASE_URL=sqlite:///dev.db uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
