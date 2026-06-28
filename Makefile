.PHONY: up down logs migrate migration-create shell test

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f bot

migrate:
	docker-compose run --rm bot alembic upgrade head

migration-create:
	docker-compose run --rm bot alembic revision --autogenerate -m "$(name)"

shell:
	docker-compose run --rm bot bash

test:
	docker-compose run --rm bot pytest