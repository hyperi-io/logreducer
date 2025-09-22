# LogReducer Development Makefile
# Provides standard make targets that call our Python development scripts
# Best of both worlds: make simplicity + Python script features

.PHONY: help setup test test-unit test-integration format lint build clean security version-check all
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)LogReducer Development Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  make setup           Set up development environment (one-time)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make format          Format code with black + isort" 
	@echo "  make lint            Run linting (flake8, mypy)"
	@echo "  make security        Run security scan"
	@echo "  make version-check   Check version consistency"
	@echo ""
	@echo "$(GREEN)Build:$(NC)"
	@echo "  make build           Build wheel/sdist packages"
	@echo "  make clean           Clean build artifacts"
	@echo ""
	@echo "$(GREEN)Workflows:$(NC)"
	@echo "  make all             Run format + lint + test + security"
	@echo ""
	@echo "$(YELLOW)Note: All commands automatically activate .venv and use professional logging$(NC)"

setup: ## Set up development environment
	@python3 scripts/setup

test: ## Run all tests
	@python3 scripts/pdev test

test-unit: ## Run unit tests only
	@python3 scripts/pdev test-unit

test-integration: ## Run integration tests only
	@python3 scripts/pdev test-integration

format: ## Format code with black + isort
	@python3 scripts/pdev format

lint: ## Run linting (flake8, mypy)
	@python3 scripts/pdev lint

build: ## Build wheel/sdist packages
	@python3 scripts/pdev build

clean: ## Clean build artifacts
	@python3 scripts/pdev clean

security: ## Run security scan
	@python3 scripts/pdev security

version-check: ## Check version consistency
	@python3 scripts/pdev version-check

all: ## Run format + lint + test + security
	@python3 scripts/pdev all

# Developer convenience targets
dev-setup: setup ## Alias for setup

test-fast: test-unit ## Run fast tests only (alias for test-unit)

check: lint ## Alias for lint

audit: security ## Alias for security

# CI/CD targets
ci-setup: ## Set up CI environment (.venv-ci)
	@python3 scripts/bootstrap

ci: ## Run full CI pipeline in .venv-ci
	@python3 scripts/ci

ci-fast: ## Run CI pipeline without slow tests
	@python3 scripts/ci --skip-slow

ci-deploy: ## Run CI pipeline and deploy to JFrog
	@python3 scripts/ci --deploy

deploy: ## Deploy to JFrog Artifactory (requires credentials)
	@python3 scripts/ci --stage deploy

# Template targets for reuse
template-help: ## Show template extraction help
	@echo "$(BLUE)Python Project Template$(NC)"
	@echo ""
	@echo "This Makefile + scripts/ structure can be extracted as a generic Python project template:"
	@echo ""
	@echo "$(GREEN)Template Components:$(NC)"
	@echo "  Makefile                     This file (generic targets)"
	@echo "  scripts/pdev                 Generic Python development commands"
	@echo "  scripts/setup                Environment setup with tool checking"
	@echo "  scripts/common.py            Professional logging + configuration"
	@echo "  scripts/security_scan.py     Comprehensive security scanning"
	@echo "  pyproject.toml               Python project configuration"
	@echo "  .github/workflows/ci.yml     CI/CD pipeline"
	@echo ""
	@echo "$(GREEN)Usage in new projects:$(NC)"
	@echo "  1. Copy template files to new project"
	@echo "  2. Update project-specific references in pyproject.toml"
	@echo "  3. Run: make setup"
	@echo "  4. Start developing with: make test, make format, etc."