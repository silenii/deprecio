# Руководство по контрибьютингу

## Git Workflow

### Ветвление
- `main` — стабильная ветка проекта и релизов.
- `codex/<type>-<краткая-задача>` — короткоживущая ветка одной задачи, например `codex/fix-market-data` или `codex/feature-price-alerts`.

Ветки создаются от актуальной `main`. Не создавайте постоянные ветки по модулям проекта. После слияния PR удаляйте рабочую ветку; старые ветки оставляйте только как исторические ссылки и не используйте для новых задач.

### Коммиты

Используйте conventional commits по формату. Описание после двоеточия пишите на русском языке:

```
<type>(<scope>): <description>
```

**Типы:**
- `feat` — новая фича
- `fix` — исправление бага
- `refactor` — рефакторинг кода
- `test` — добавление тестов
- `docs` — документация
- `chore` — рутина, зависимости
- `perf` — улучшение производительности

## Публикация в GitHub и GitVerse

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/fix-краткое-описание
git push -u origin codex/fix-краткое-описание
git push -u gitverse codex/fix-краткое-описание
```

Открывайте Pull Request в GitHub в `main`. Используйте **Squash and merge**. После слияния обновляйте зеркало GitVerse вручную: `git switch main; git pull --ff-only origin main; git push gitverse main`. Не отправляйте рабочие коммиты напрямую в `main`.

## Правила к коду
- Python 3.11+
- Type hints для всех функций
- Docstrings для основных классов
- Покрытие тестами >= 70%
- Соблюдение PEP 8

## Рабочий цикл

1. Обновить локальный `main` из GitHub и создать `codex/<type>-<задача>`.
2. Делать небольшие логические коммиты по-русски.
3. Обновить документацию, если изменилось поведение проекта.
4. Запустить проверки и отправить ветку в GitHub и GitVerse.
5. Открыть PR в GitHub, дождаться CI и выполнить Squash and merge.
6. Обновить `main` в GitVerse и удалить рабочие ветки после принятия.

## Локальная проверка

Перед Pull Request выполните из корня репозитория в PowerShell:

```powershell
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m pytest tests/ -v --cov=deprecio --cov-report=term-missing --cov-fail-under=70
.venv/Scripts/python.exe -m ruff check deprecio/
docker build --target runtime -t deprecio:local .
```

Последовательность должна пройти полностью; минимальный порог покрытия — 70%.
