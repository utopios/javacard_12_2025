# =============================================================================
# Makefile - JavaCard Docker Emulator
# =============================================================================

.PHONY: all build up down restart logs clean test help

# Configuration
COMPOSE = docker compose
PROJECT_NAME = javacard-emulator

# Couleurs
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
CYAN   := $(shell tput -Txterm setaf 6)
RESET  := $(shell tput -Txterm sgr0)

# =============================================================================
# Cibles principales
# =============================================================================

all: build up ## Build and start all services

build: ## Build all Docker images
	@echo "$(CYAN)Building Docker images...$(RESET)"
	$(COMPOSE) build

up: ## Start all services
	@echo "$(GREEN)Starting services...$(RESET)"
	$(COMPOSE) up -d
	@echo "$(GREEN)Services started!$(RESET)"
	@echo ""
	@echo "$(YELLOW)Available endpoints:$(RESET)"
	@echo "  - jCardSim socket: localhost:9025"
	@echo ""
	@echo "$(YELLOW)To interact with the emulator:$(RESET)"
	@echo "  make shell        # Open test client shell"
	@echo "  make apdu-shell   # Open APDU interactive shell"
	@echo "  make test         # Run applet tests"

down: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(RESET)"
	$(COMPOSE) down

restart: down up ## Restart all services

logs: ## Show logs from all services
	$(COMPOSE) logs -f

logs-jcardsim: ## Show jCardSim logs
	$(COMPOSE) logs -f jcardsim

logs-pcsc: ## Show PC/SC bridge logs
	$(COMPOSE) logs -f pcsc-bridge

# =============================================================================
# Interaction
# =============================================================================

shell: ## Open shell in test client container
	@echo "$(CYAN)Opening test client shell...$(RESET)"
	$(COMPOSE) exec test-client /bin/bash

opensc-shell: ## Open shell in OpenSC middleware container
	$(COMPOSE) exec opensc-middleware /bin/bash

apdu-shell: ## Open APDU interactive shell
	@echo "$(CYAN)Opening APDU shell...$(RESET)"
	$(COMPOSE) exec test-client python3 /app/scripts/apdu-shell.py

send-apdu: ## Send APDU command (usage: make send-apdu APDU=00A4040007...)
	@if [ -z "$(APDU)" ]; then \
		echo "$(YELLOW)Usage: make send-apdu APDU=00A4040007F0000000010001$(RESET)"; \
	else \
		$(COMPOSE) exec test-client python3 /app/scripts/send-apdu.py "$(APDU)"; \
	fi

# =============================================================================
# Tests
# =============================================================================

test: ## Run all applet tests
	@echo "$(CYAN)Running applet tests...$(RESET)"
	$(COMPOSE) exec test-client python3 /app/scripts/test-applet.py

test-pkcs11: ## Run PKCS#11 tests
	@echo "$(CYAN)Running PKCS#11 tests...$(RESET)"
	$(COMPOSE) exec opensc-middleware python3 /app/scripts/pkcs11-test.py

test-verbose: ## Run tests in verbose mode
	$(COMPOSE) exec test-client python3 /app/scripts/test-applet.py --verbose

# =============================================================================
# Compilation d'applets
# =============================================================================

compile: ## Compile example applet
	@echo "$(CYAN)Compiling HelloWorld applet...$(RESET)"
	$(COMPOSE) exec test-client /app/scripts/compile-applet.sh \
		/app/applets/src \
		-a F0000000010001 \
		-c com.example.helloworld.HelloWorldApplet

install: ## Install compiled applet
	@echo "$(CYAN)Installing applet...$(RESET)"
	$(COMPOSE) exec test-client /app/scripts/install-applet.sh install /app/applets/HelloWorldApplet.cap

list-applets: ## List installed applets
	$(COMPOSE) exec test-client /app/scripts/install-applet.sh list

# =============================================================================
# OpenSC Tools
# =============================================================================

opensc-utils: ## Run OpenSC utilities menu
	$(COMPOSE) exec opensc-middleware /app/scripts/opensc-utils.sh

pcsc-scan: ## Scan for PC/SC readers
	$(COMPOSE) exec opensc-middleware pcsc_scan

card-info: ## Show card information
	$(COMPOSE) exec opensc-middleware opensc-tool --info

# =============================================================================
# Maintenance
# =============================================================================

clean: down ## Stop and remove containers, networks, volumes
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	$(COMPOSE) down -v --rmi local
	rm -rf ./data/*
	@echo "$(GREEN)Cleanup complete$(RESET)"

clean-data: ## Clear persistent data only
	@echo "$(YELLOW)Clearing persistent data...$(RESET)"
	$(COMPOSE) down
	docker volume rm $(PROJECT_NAME)_jcardsim-data $(PROJECT_NAME)_shared-data 2>/dev/null || true
	@echo "$(GREEN)Data cleared$(RESET)"

status: ## Show status of all services
	@echo "$(CYAN)Services status:$(RESET)"
	$(COMPOSE) ps

health: ## Check health of all services
	@echo "$(CYAN)Health check:$(RESET)"
	@echo ""
	@echo "jCardSim:"
	@nc -z localhost 9025 && echo "  $(GREEN)✓ Socket accessible$(RESET)" || echo "  $(YELLOW)✗ Socket not accessible$(RESET)"
	@echo ""
	@echo "Containers:"
	@$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}"

# =============================================================================
# Development helpers
# =============================================================================

dev: ## Start in development mode (attached)
	$(COMPOSE) up

rebuild: ## Force rebuild of all images
	$(COMPOSE) build --no-cache

pull: ## Pull latest base images
	$(COMPOSE) pull

# =============================================================================
# Mac-specific helpers
# =============================================================================

mac-setup: ## Setup for macOS (install dependencies)
	@echo "$(CYAN)Setting up for macOS...$(RESET)"
	@which docker >/dev/null || (echo "$(YELLOW)Please install Docker Desktop first$(RESET)" && exit 1)
	@which docker-compose >/dev/null || brew install docker-compose
	@echo "$(GREEN)Setup complete!$(RESET)"

mac-test-connection: ## Test connection from Mac host
	@echo "$(CYAN)Testing jCardSim connection...$(RESET)"
	@python3 scripts/send-apdu.py --host localhost --port 9025 "00A40400" || \
		echo "$(YELLOW)Hint: Make sure services are running with 'make up'$(RESET)"

# =============================================================================
# Help
# =============================================================================

help: ## Show this help
	@echo ""
	@echo "$(CYAN)JavaCard Docker Emulator$(RESET)"
	@echo "========================="
	@echo ""
	@echo "$(YELLOW)Usage:$(RESET)"
	@echo "  make [target]"
	@echo ""
	@echo "$(YELLOW)Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Quick Start:$(RESET)"
	@echo "  1. make build      # Build images"
	@echo "  2. make up         # Start services"
	@echo "  3. make test       # Run tests"
	@echo "  4. make apdu-shell # Interactive APDU shell"
	@echo ""
