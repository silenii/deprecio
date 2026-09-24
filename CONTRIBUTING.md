# Руководство по контрибьютингу

## Git Workflow

### Ветвление
- `main` — production branch (стабильные релизы)
- `dev` — integration branch (для сборки фич)
- `feature/*` — feature branches (новые фичи)
- `hotfix/*` — hotfix branches (срочные багфиксы)

### Коммиты

Используйте conventional commits по формату:

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

```bash
git remote add github https://github.com/silenii/deprecio.git
git remote add gitverse https://gitverse.ru/silenii/deprecio.git

git push github main
git push gitverse main
```

## Правила к коду
- Python 3.11+
- Type hints для всех функций
- Docstrings для основных классов
- Покрытие тестами >= 70%
- Соблюдение PEP 8
