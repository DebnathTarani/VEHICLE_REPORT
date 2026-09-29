###############################################################################
# Makefile — Docker shortcuts
###############################################################################

APP_PORT ?= 5010
DOCKER_COMPOSE      = docker compose
DOCKER_COMPOSE_PROD = docker compose -f docker-compose.prod.yml

# ── Development ────────────────────────────────────────────────────────────

.PHONY: dev up-down build-dev clean-dev logs-dev ps-dev

dev:      ## up development stack
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) up -d --build

up-dev:  ## up development stack
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) up -d --build

down-dev: ## down development stack
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) down

build-dev: ## build without up
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) build

logs-dev: ## follow dev logs
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) logs -f

ps-dev: ## list containers
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) ps

clean-dev: ## down + remove volumes (db gone!)
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE) down -v

# ── Production ─────────────────────────────────────────────────────────────

.PHONY: prod up-prod build-prod clean-prod logs-prod ps-prod

prod:     ## up production stack
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) up -d --build

up-prod:  ## override app port default
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) up -d --build

down-prod: ## stop production containers
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) down

build-prod: ## build production image
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) build

logs-prod: ## follow production logs
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) logs -f

ps-prod: ## list production containers
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) ps

clean-prod: ## stop + remove volumes
	APP_PORT=$(APP_PORT) $(DOCKER_COMPOSE_PROD) down -v

# ── Belt-and-suspenders: raw Docker ───────────────────────────────────────

.PHONY: build-raw run-raw down-raw logs-raw

build-raw: ## build image raw
	docker build -t vehicle-report -f Dockerfile .

run-raw:  ## run image raw
	docker run -d -p $(APP_PORT):5010 --name vehicle-report -v data:/data -e VEHICLE_REPORT_DB=/app/data/vehicle_reports.db vehicle-report

down-raw: ## down raw
	docker rm -f vehicle-report

logs-raw: ## raw raw
	docker logs -f vehicle-report
