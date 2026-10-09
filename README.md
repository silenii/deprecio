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
- FastAPI API с маршрутами устройств, истории цен и прогнозов;
- веб-клиент аналитики на vanilla HTML/CSS/JavaScript без отдельного frontend-фреймворка;
- CLI-точка входа `deprecio`.

В прогнозе `predicted_rv_percent` означает прогнозную цену в процентах от
переданной текущей цены (`current_price_rub`), а не от MSRP. Профиль прогноза
принимает `0 <= brand_decay_monthly_rate < 1`, неотрицательный
`historical_plateau_rv` и положительный `expected_sweet_spot_months`.
Если рассчитанное плато выше текущей цены, оно ограничивается текущей ценой,
поэтому модель не прогнозирует рост стоимости.

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

API по умолчанию использует `CachedSpecsProvider`: он читает основной каталог из `data/catalog.json` и при необходимости ищет дополнительные устройства в `data/global_devices.db`. Тесты и интеграции могут заменить его через FastAPI `app.dependency_overrides`.

### API аналитики

| Метод и маршрут | Назначение |
|---|---|
| `GET /api/v1/analytics/compare?model_ids=...` | Сравнение 2-5 устройств: нормализованные характеристики, MSRP, текущая цена, RV, depreciation drop, forecast summary и market stats. |
| `GET /api/v1/analytics/analogs/{model_id}` | Подбор аналогов с параметрами `tier`, `budget_min_rub`, `budget_max_rub`, `limit`. |
| `GET /api/v1/analytics/devices/{model_id}/market` | Рыночная карточка с медианой, диапазонами, количеством объявлений и датой обновления. |
| `GET /api/v1/reports/{model_id}?format=json` | Скачать карточку устройства в `json`, `csv`, `html` или `md`. |
| `GET /api/v1/reports/compare/download?model_ids=...&format=csv` | Скачать сравнение 2-5 устройств. |

Ошибки используют стабильный формат `{"code": "...", "message": "...", "details": null}`. Коды: `not_found`, `http_error`, `validation_error`.

```bash
curl "http://localhost:8000/api/v1/analytics/compare?model_ids=xiaomi-14&model_ids=xiaomi-14"
curl "http://localhost:8000/api/v1/analytics/analogs/xiaomi-14?tier=Flagship&budget_max_rub=100000&limit=5"
curl "http://localhost:8000/api/v1/analytics/devices/xiaomi-14/market"
```

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/analytics/compare?model_ids=xiaomi-14&model_ids=xiaomi-14"
Invoke-RestMethod "http://localhost:8000/api/v1/analytics/analogs/xiaomi-14?tier=Flagship&budget_max_rub=100000&limit=5"
Invoke-RestMethod "http://localhost:8000/api/v1/analytics/devices/xiaomi-14/market"
```

Отчёты содержат только публичные рассчитанные поля, версию формата и UTC-время
формирования. Примеры скачивания:

```bash
curl -OJ "http://localhost:8000/api/v1/reports/xiaomi-14?format=json"
curl -OJ "http://localhost:8000/api/v1/reports/compare/download?model_ids=xiaomi-14&model_ids=oneplus-12&format=html"
deprecio report-export --model-id xiaomi-14 --format csv --output report.csv
deprecio report-export --model-id xiaomi-14 --model-id oneplus-12 --format md
```

Стек: Python 3.11+, Pydantic, FastAPI, aiogram, pytest, Ruff и Docker.

### Веб-клиент аналитики

Отдельный frontend-стек в проекте ранее не был выбран: отсутствуют `package.json`,
Node-зависимости и frontend-сборщик. Поэтому клиент реализован как небольшой
vanilla HTML/CSS/JavaScript в `frontend/`, который FastAPI отдаёт по адресу `/`.
Он использует существующие схемы API без дублирования расчётов. Результат поиска
сохраняется в `?q=...`, карточка устройства в `?device=...`; обе ссылки можно
передавать другим пользователям.

Запуск веб-клиента локально:

```powershell
.venv/Scripts/python.exe -m uvicorn deprecio.api.main:app --reload
# открыть http://127.0.0.1:8000/
```

Клиент показывает состояния загрузки, пустого результата, ошибки API и отсутствующих
market data. График истории строится из поля `chart` маршрута price-history, а
прогноз и сравнение используют соответствующие существующие API-маршруты.

## Структура `data/`

| Путь | Назначение |
|---|---|
| `data/catalog.json` | Исходный демонстрационный каталог: `model_id`, бренд, серия, чипсет, региональные editions, аппаратные особенности, комплектации, варианты памяти и профиль прогноза. |
| `data/global_devices.db` | Предсобранная SQLite-база глобального каталога для быстрого локального поиска без внешних источников. |
| `data/price_history.db` | SQLite-хранилище исторических снимков рыночных цен, создаётся автоматически при первом обращении API. |
| `data/modern_supplement.json` | Дополнительный набор современных моделей для пополнения каталога. |
| `data/templates/device_template.yaml` | Шаблон YAML для добавления нового устройства. |

Скрипты `scripts/build_global_db.py` и `scripts/patch_db.py` предназначены для сборки и обновления SQLite-базы. Бинарную базу не следует редактировать вручную.

Проверка каталога выполняется командой `deprecio catalog-diagnose --json`; при любой ошибке она завершается с кодом `1`. Воспроизводимая пересборка из источника выполняется командой `python scripts/build_global_db.py --catalog data/catalog.json --output data/global_devices.db`. Скрипт создаёт временную базу, перестраивает индексы и атомарно заменяет `data/global_devices.db`.

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

После установки доступна команда `deprecio`.

### Проверка ценовых алертов по расписанию

Команда выполняет одну проверку и завершает процесс. Без токена Telegram события
выводятся в JSON-логе; `--dry-run` дополнительно отключает отправку уведомлений:

```powershell
$env:DEPRECIO_BOT_TOKEN = "123456:token"
deprecio check-alerts
deprecio check-alerts --dry-run
```

Пример задания Windows Task Scheduler, запускающего проверку каждый час:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\Projects\Deprecio\.venv\Scripts\deprecio.exe" -Argument "check-alerts"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "Deprecio price alerts" -Action $action -Trigger $trigger -RunLevel Highest
```

Перед регистрацией задайте `DEPRECIO_BOT_TOKEN` в окружении пользователя или
используйте `.env`; лимит одной проверки настраивается через
`DEPRECIO_ALERT_CHECK_TIMEOUT_SEC` (по умолчанию 60 секунд).

### Сбор снимков истории цен

В PowerShell можно собрать снимок одной модели или пройти весь каталог:

```powershell
deprecio harvest-snapshot --model-id xiaomi-14 --source avito
deprecio harvest-all --source avito
deprecio harvest-all --dry-run
```

Снимки сохраняются в `data/price_history.db`. Повторный запуск для той же модели,
источника и даты заменяет существующий снимок; `--dry-run` выполняет сбор без записи.

## Запуск через Docker

Создайте `.env`, затем соберите и запустите сервис:

```bash
docker compose up --build
```

`Dockerfile` собирает production-образ на Python 3.11, копирует пакет и `data/`, а контейнер запускает `python -m deprecio.bot.main`. Compose передаёт настройки из `.env` и сохраняет кэш в volume `deprecio-cache`.

## Единая локальная проверка

В PowerShell из корня репозитория выполните последовательность, совпадающую с CI:

```powershell
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m pytest tests/ -v --cov=deprecio --cov-report=term-missing --cov-fail-under=70
.venv/Scripts/python.exe -m ruff check deprecio/
docker build --target runtime -t deprecio:local .
```

`make check` выполняет тесты с покрытием и Ruff, а `make docker-build` собирает runtime-образ. Makefile не содержит Unix-only команд и подходит для GNU Make в PowerShell.

## Синхронизация

### Избранное Telegram

При первом запуске бот создаёт `data/favorites.db` (SQLite) с таблицей `favorites`: `user_id`, `model_id`, `created_at`; первичный ключ пары `user_id/model_id` предотвращает дубли. Данные принадлежат Telegram `user_id`, без отдельной авторизации. Команда `/favorites` и кнопка меню показывают максимум 10 записей на страницу с навигацией. FSM и тексты сообщений в это хранилище не записываются.

```bash
git push origin main
git push gitverse main
```

## Лицензия

MIT.