COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: db-up db-down db-logs db-shell up down logs

## Database only
db-up:
	$(COMPOSE) up postgres -d

db-down:
	$(COMPOSE) down

db-logs:
	$(COMPOSE) logs -f postgres

db-shell:
	docker exec -it hr-screening-db psql -U bot -d hr_screening

## Full stack
up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f
