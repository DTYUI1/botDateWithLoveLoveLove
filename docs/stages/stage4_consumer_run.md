# Stage4 consumer runtime check

**Дата:** 2026-05-11
**Команда запуска:**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d \
  rabbitmq minio prometheus grafana celery_worker celery_beat \
  swipe_consumer match_consumer
```

## Результат

`swipe_consumer` и `match_consumer` подняты как отдельные сервисы prod-overlay
и прошли healthcheck после замены `pgrep` на Python-проверку `/proc`:

```text
connectme-match_consumer-1   Up ... (healthy)
connectme-swipe_consumer-1   Up ... (healthy)
```

Логи подтверждают подключение к RabbitMQ и обработку событий:

```text
[Consumer:match_notifications] подключён
[Consumer:swipe_processing] подключён
[SwipeConsumer] триггер точечного пересчёта рейтинга
```

Итог: пункт 3.3.5 закрыт стендовым запуском, а healthcheck больше не зависит
от утилит `pgrep`/`ps`, отсутствующих в slim Python images.
