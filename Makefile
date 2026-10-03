.PHONY: install test test-cov lint check docker-build bot

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ -v --cov=deprecio --cov-report=term-missing --cov-fail-under=70

lint:
	python -m ruff check deprecio/

check: test-cov lint

docker-build:
	docker build --target runtime -t deprecio:local .

bot:
	python -m deprecio.bot.main
