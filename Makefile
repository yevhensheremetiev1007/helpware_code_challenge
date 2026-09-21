.DEFAULT_GOAL := help

COMPOSE := docker compose
PSQL := $(COMPOSE) exec -T postgres psql -U rubric -d rubric

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: up
up: ## Start the whole stack
	$(COMPOSE) up -d --build
	@echo ""
	@echo "API      http://localhost:8080"
	@echo "Frontend http://localhost:5173  (first start takes a minute: npm install)"
	@echo ""
	@echo "Next: make seed"

.PHONY: down
down: ## Stop the stack
	$(COMPOSE) down

.PHONY: reset
reset: ## Stop the stack and delete all data
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Follow API logs
	$(COMPOSE) logs -f api-1 api-2

.PHONY: migrate
migrate: ## Apply database migrations
	$(COMPOSE) run --rm migrate alembic upgrade head

.PHONY: seed
seed: migrate ## Load test data. Override size with SEED_CONVERSATIONS=20000
	$(COMPOSE) run --rm -e SEED_CONVERSATIONS=$${SEED_CONVERSATIONS:-2000} migrate \
		python -m scripts.seed

.PHONY: repro-interactive
repro-interactive: ## 20 supervisors click "re-score" at the same time
	$(COMPOSE) run --rm migrate python -m scripts.load_test interactive

.PHONY: repro-batch
repro-batch: ## Submit a night of conversations the way the scheduled job does
	$(COMPOSE) run --rm migrate python -m scripts.load_test batch

.PHONY: repro-webhook
repro-webhook: ## Replay conversation-closed webhooks the way a client helpdesk does
	$(COMPOSE) run --rm migrate python -m scripts.load_test webhook

.PHONY: score-report
score-report: ## Show score rows per conversation and totals
	@$(PSQL) -f /dev/stdin < scripts/score_report.sql

.PHONY: psql
psql: ## Open a database shell
	$(COMPOSE) exec postgres psql -U rubric -d rubric

.PHONY: test
test: migrate ## Run the test suite
	$(COMPOSE) run --rm migrate pytest -q

.PHONY: health
health: ## Ask the load balancer for service health
	@curl -s -w '\nHTTP %{http_code} in %{time_total}s\n' http://localhost:8080/health
