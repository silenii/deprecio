# 📉 Deprecio

Аналитический движок и Telegram-бот для поиска смартфонов, анализа остаточной стоимости и прогнозирования снижения цен на вторичном рынке.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Возможности

- каталог устройств с региональными версиями, характеристиками и комплектациями;
- fuzzy-поиск по бренду, модели и серии;
- очистка и агрегация объявлений рынка;
- расчёт остаточной стоимости, сравнение поколений и прогноз снижения цены;
- Telegram-бот на `aiogram`;
- FastAPI API с маршрутами устройств и прогнозов;
- CLI-точка входа `deprecio`.

## Архитектура

```text
deprecio/
├── api/          FastAPI-приложение и HTTP-маршруты /api/v1
├── bot/          aiogram-бот, конфигурация, зависимости, handlers и keyboards
├── cleaner/      правила фильтрации и санитизации объявлений
├── cli/          консольная точка входа
├── core/         fuzzy-поиск, метрики и аналитические значения по умолчанию
├── forecast/     расчёты прогноза падения цены
├── harvester/    модели, сбор и агрегация рыночных объявлений
├── models/       доменные Pydantic-модели устройств и объявлений
└── providers/    локальный каталог, кэшированный провайдер и внешние адаптеры
```

`data/` содержит исходные данные и локальное хранилище каталога. Бот создаёт провайдеры каталога и агрегатор рынка, регистрирует роутеры и запускает long polling. API подключает маршруты устройств и прогнозов под префиксом `/api/v1`.

Стек: Python 3.11+, Pydantic, FastAPI, aiogram, pytest, Ruff и Docker.

## Структура `data/`

| Путь | Назначение |
|---|---|
| `data/catalog.json` | Исходный демонстрационный каталог: `model_id`, бренд, серия, чипсет, региональные editions, аппаратные особенности, комплектации, варианты памяти и профиль прогноза. |
| `data/global_devices.db` | Предсобранная SQLite-база глобального каталога для быстрого локального поиска без внешних источников. |
| `data/modern_supplement.json` | Дополнительный набор современных моделей для пополнения каталога. |
| `data/templates/device_template.yaml` | Шаблон YAML для добавления нового устройства. |

Скрипты `scripts/build_global_db.py` и `scripts/patch_db.py` предназначены для сборки и обновления SQLite-базы. Бинарную базу не следует редактировать вручную.

## Запуск через Poetry

Требуется Python 3.11 или новее и Poetry.

```bash
poetry install
poetry run python -m deprecio.bot.main
```

Перед запуском создайте `.env` из `.env.example` и укажите токен Telegram:

```bash
cp .env.example .env
# DEPRECIO_BOT_TOKEN=...
```

Проверка API локально:

```bash
poetry run uvicorn deprecio.api.main:app --reload
```

## Запуск через venv и pip

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m deprecio.bot.main
```

После установки доступна команда `deprecio`. Для разработки используются `pytest tests/ -v` и `ruff check deprecio/`.

## Запуск через Docker

Создайте `.env`, затем соберите и запустите сервис:

```bash
docker compose up --build
```

`Dockerfile` собирает production-образ на Python 3.11, копирует пакет и `data/`, а контейнер запускает `python -m deprecio.bot.main`. Compose передаёт настройки из `.env` и сохраняет кэш в volume `deprecio-cache`.

## Тесты и линтер

```bash
pytest tests/ -v
ruff check deprecio/
```

## Синхронизация

```bash
git push origin main
git push gitverse main
```

## Лицензия

MIT.