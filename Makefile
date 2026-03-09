COMPOSE ?= docker compose

.PHONY: up down logs migrate test lint format

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

migrate:
	$(COMPOSE) exec app alembic upgrade head

test:
	$(COMPOSE) exec app pytest -q

lint:
	$(COMPOSE) exec app ruff check app tests
	$(COMPOSE) exec app mypy app

format:
	$(COMPOSE) exec app ruff format app tests
