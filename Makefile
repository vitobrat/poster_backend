.PHONY: help install-lint lint

## help: Показать все доступные команды
help:
	@echo "Доступные команды:"
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'

## install-lint: Установить pre-commit хуки
install-lint:
	pre-commit install

## lint: Запустить линтеры на всех файлах
lint:
	pre-commit run --all-files

deploy_dev:
	docker compose -f docker-compose.dev.yml up -d
	uv run alembic upgrade head
	uv run uvicorn src.main:app --reload
