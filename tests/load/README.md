# Нагрузочное тестирование (Locust)

> Согласовано c PM как замена JMeter: легче запускать в CI, сценарии на Python,
> CSV-отчёты пишутся из коробки.

## Запуск локально

```bash
# Опциональная установка
pip install locust httpx

# Засидить БД 100 фейковыми пользователями.
# Если backend-контейнер запущен, seed.sh возьмёт его DATABASE_URL.
bash tests/load/seed.sh 100

# Headless-прогон на 60 секунд, 50 пользователей, ramp 10/sec
mkdir -p tests/load/results
locust \
  -f tests/load/locustfile.py \
  --host http://localhost:8005 \
  --users 50 \
  --spawn-rate 10 \
  --run-time 60s \
  --headless \
  --csv tests/load/results/run \
  --csv-full-history
```

После прогона смотрим `tests/load/results/run_*.csv`. p50/p95/p99 и error rate
описаны в отчёте `docs/stages/stage4_loadtest.md`.

## Сценарий

Каждый «пользователь» в Locust имитирует один цикл:

1. `POST /api/v1/auth/telegram` — создаёт/получает пользователя.
2. `POST /api/v1/profile` — создаёт анкету load-пользователя, если её ещё нет.
3. `GET /api/v1/matching/next` — забирает следующую анкету.
4. `POST /api/v1/matching/swipe` — отправляет случайный лайк/пас.

Время между шагами — нормальное распределение 0.5–2.0 сек.

## Целевые SLA

| Метрика | Цель |
|---|---|
| p95 `/matching/next` | < 250 ms |
| p95 `/matching/swipe` | < 350 ms |
| Error rate | < 1% |
| Endpoint-focused throughput | >= 50 RPS на проверяемый endpoint |

## Endpoint-focused профиль

Mixed-сценарий проверяет пользовательский путь целиком, но из-за think-time и
распределения задач не обязан давать 50 RPS на каждый endpoint. Для строгой
проверки throughput используется отдельный профиль:

```bash
# Preseed: 800 candidate profiles + 120 requester profiles
bash tests/load/seed.sh 800 120

# Target для swipe-профиля можно взять из БД:
docker compose exec -T db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At \
   -c "select id from profiles where gender = '\''female'\'' and city = '\''LoadCity'\'' limit 1;"'

# /matching/next
LOCUST_PRESEEDED_REQUESTERS=120 \
LOCUST_RPS_PER_USER=2.05 \
LOCUST_ENDPOINT=next locust \
  -f tests/load/locustfile_endpoint.py \
  --host http://localhost:8005 \
  --users 25 \
  --spawn-rate 50 \
  --run-time 60s \
  --headless \
  --csv tests/load/results/endpoint_next \
  --csv-full-history

# /matching/swipe
LOCUST_PRESEEDED_REQUESTERS=120 \
LOCUST_TARGET_PROFILE_ID=<female_profile_uuid_from_seed> \
LOCUST_RPS_PER_USER=2.6 \
LOCUST_ENDPOINT=swipe locust \
  -f tests/load/locustfile_endpoint.py \
  --host http://localhost:8005 \
  --users 20 \
  --spawn-rate 50 \
  --run-time 60s \
  --headless \
  --csv tests/load/results/endpoint_swipe \
  --csv-full-history
```

## CI

В CI этот прогон **не** запускается по умолчанию — он требует поднятой
инфраструктуры. Запустить вручную: `workflow_dispatch` job `loadtest`
(см. `.github/workflows/ci.yml`).
