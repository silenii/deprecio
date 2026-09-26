.PHONY: install test test-cov lint bot clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=deprecio --cov-report=term-missing

lint:
	python -m py_compile deprecio/**/*.py && echo "Syntax OK"

bot:
	python -m deprecio.bot.main

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
