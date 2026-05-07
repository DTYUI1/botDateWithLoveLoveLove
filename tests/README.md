# Tests

В проекте два набора тестов с разной зависимостью от инфраструктуры.

## `tests/` — unit-тесты (этот каталог)

Полностью замокированы (AsyncSession, MinIOClient, Redis). Не требуют поднятых сервисов.

```bash
.venv/bin/python -m pytest tests/ -v
```

Покрывают:

- `test_api_endpoints.py` — health-check, auth, базовые smoke-проверки.
- `test_stage3_integration.py` — рейтинги (Primary/Behavioral/Combined), Redis cache patterns на моках.
- `test_messages_api.py` — `MessageService` (отправка, валидация, постраничный список).
- `test_date_ideas_api.py` — `DateIdeaService` (CRUD, ранжирование по интересам/городу, feedback).
- `test_photos_minio.py` — `PhotoService` (валидация, лимит 6 фото, MinIO upload/delete через мок).
- `test_celery_tasks.py` — регистрация Celery-задач и beat schedule.

## `test/` — интеграционные тесты

Требуют живые PostgreSQL, Redis, RabbitMQ (поднятые через `docker-compose.infra.yml`). Пропускаются, если сервисы недоступны.

```bash
docker compose -f docker-compose.infra.yml up -d
.venv/bin/python -m pytest test/ -v
```

## Запуск всего сразу

```bash
bash scripts/run-tests.sh
```

Скрипт сначала прогоняет unit-тесты, затем интеграционные (без падения сборки, если последние недоступны).
