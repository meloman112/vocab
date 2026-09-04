.DEFAULT_GOAL := help
COMPOSE := docker compose

help: ## Список команд
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

up: ## Собрать и поднять всё
	$(COMPOSE) up -d --build

down: ## Остановить
	$(COMPOSE) down

logs: ## Логи api и бота
	$(COMPOSE) logs -f api bot

ps: ## Статус контейнеров
	$(COMPOSE) ps

psql: ## Консоль базы
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-vocab} -d $${POSTGRES_DB:-vocab}

front: ## Пересобрать мини-апп локально (в контейнере это делает Dockerfile)
	cd miniapp && npm ci && npm run build

xpi: ## Собрать расширение в extension/vocab.xpi
	@cd extension && rm -f ../vocab.xpi && zip -q -r -FS ../vocab.xpi . && \
	 echo "собрано: $(CURDIR)/vocab.xpi"

test: ## Тесты backend
	cd backend && python -m pytest

env-check: ## Все ключи из .env.example есть в .env
	@python3 scripts/env_check.py

smoke: ## Проверить живой контур
	@python3 scripts/smoke.py

.PHONY: help up down logs ps psql front xpi test env-check smoke
