# Аудит соответствия tracking-fix.md фактическому состоянию

**Дата:** 2026-05-11
**Ветка:** `stage4`
**Аудитор:** AI-аудитор (роль `promts/auditor.md`)
**Источники:**
- Требования: `promts/requirements/req.md`
- План: `promts/data/plan-fix/plan-fix.md`
- Чек-лист, который проверяем: `promts/data/plan-fix/tracking-fix.md`
- DevOps-отчёт: `promts/data/devops-report/devops-report.md`
- Stage4 отчёт: `docs/stages/stage4_report.md`
- Stage4 loadtest: `docs/stages/stage4_loadtest.md`

---

## 1. Краткое резюме

Из 44 задач в `tracking-fix.md` фактически подтверждено **35 полностью**
выполненных и **6 частично** (✅ и 🟡 в плане совпадают с фактическим
состоянием кода). 3 пункта «в очереди» (А.2–А.4 — аудиторская верификация)
закрываются текущим документом и финальной фазой.

Главный вывод: tracking-fix.md **не завышает статус** в кодовой части —
все ✅ подтверждаются файлами и локальным прогоном (`ruff`, `pytest 67
passed`, CSV-артефакты Locust, рабочий compose-конфиг). Расхождения с
фактом носят либо документационный (несколько мест в README/stage4_report
рассинхронизированы), либо «деплойный» характер (изменения не закоммичены,
поэтому CI бейдж и `audit-final.md` ещё не имеют реального подтверждения).

Балл по `req.md` ориентировочно поднимается с ~22 до **27–28** за счёт
CI/CD (+1), MQ-consumer'ов (+1), Celery (+1), бизнес-метрик (+1),
нагрузочного отчёта (+1). До «5» (30+) не хватает одного дополнительного
этапа (notification-сервис уже частично есть, его можно явно засчитать
+3 при согласовании с PM).

---

## 2. Проверенные требования (соответствие tracking-fix.md)

### Кодовые претензии — подтверждены фактически

- [x] `.github/workflows/ci.yml` — 4 jobs (lint/tests/build/secret-scan),
  бейдж в `README.md:3`. Локально `ruff check backend bot tests` —
  «All checks passed!», `pytest tests -q` — **67 passed, 3 warnings**.
- [x] `tests/load/locustfile.py`, `tests/load/seed.sh`,
  `tests/load/seed_load_data.py`, `tests/load/README.md` присутствуют.
- [x] CSV-артефакты в `tests/load/results/`: `run_*`, `full_*`, `stress_*`,
  `seed.log`. Аггрегат `full_stats.csv` — **4019 requests, 0 failures,
  68 RPS**; `stress_stats.csv` — **5756 requests, 0 failures, 97 RPS,
  p95 swipe 870 ms** (превышение SLA честно зафиксировано в отчёте).
- [x] `backend/workers/base_consumer.py` — retry увеличивает `x-retries`
  через republish (см. `_republish_for_retry`, строки 85–106) и шлёт в DLQ
  по достижении `max_retries`. `bot/workers/base_consumer.py` — аналогично.
- [x] `infrastructure/rabbitmq/definitions.json` декларирует DLX и 4 `.dlq`,
  что подтверждено `infrastructure/rabbitmq/event_publisher.py` (`dlx`
  exchange, `*.dlq` queues, аргументы `x-dead-letter-*`).
- [x] `backend/workers/swipe_consumer.py` триггерит
  `recalculate_profile_rating.delay(...)` Celery-task.
- [x] `bot/workers/match_consumer.py` отправляет push через `bot.send_message`
  и инкрементит `BOT_PUSH_DELIVERED_TOTAL/BOT_PUSH_FAILED_TOTAL`.
- [x] Endpoint `GET /api/v1/profile/{profile_id}/telegram_id` есть в
  `backend/api/v1/profile.py:21-35`.
- [x] `backend/core/mq.py` — singleton publisher с
  `init_event_publisher/close_event_publisher/safe_publish` и
  fail-safe-логикой.
- [x] `backend/core/minio.py` — singleton с `init_minio_client/get_minio_client`.
- [x] `infrastructure/rabbitmq/event_publisher.py` — топология декларируется
  один раз (`self._topology_declared`), реконнект через `connect_robust`
  и `passive=True`.
- [x] `backend/tasks/photo_tasks.py` — Pillow `image.verify()` + thumbnail
  512×512 → JPEG, статус модерации обновляется (`approved`/`rejected`).
- [x] `backend/tasks/rating_tasks.py`, `notification_tasks.py` существуют.
- [x] Celery `.delay()`-вызовы из API подтверждены:
  `backend/api/v1/matching.py:135-150` (rating + match push),
  `backend/api/v1/photos.py:103-108` (`process_photo`).
- [x] `backend/core/metrics.py` определяет 7 кастомных метрик; в
  `matching.py` они реально инкрементируются: `SWIPES_TOTAL.labels(action)`,
  `MATCHES_TOTAL`, `CACHE_HITS/MISSES`, `SWIPE_DURATION.time()`.
- [x] `bot/metrics.py` — счётчики + aiohttp `/metrics`; в `bot/main.py:105`
  поднимается через `start_metrics_server(...)`.
- [x] `infrastructure/prometheus/prometheus.yml` содержит job
  `connectme-bot` (target `bot:8001`).
- [x] `infrastructure/grafana/provisioning/dashboards/connectme.json`
  расширен бизнес-панелями: «Свайпы / минуту», «Мэтчи / минуту»,
  «p95 swipe duration», «Cache hit ratio», «Глубина очередей», «DLQ depth»,
  «MQ publish errors/ok», «Обновления бота», «Callbacks / min», «Доставка
  push'ей», «Ошибки API-клиента бота».
- [x] Compose без дефолтов: `docker-compose.yml`, `docker-compose.prod.yml`
  используют `${VAR:?…}` для всех чувствительных переменных; MinIO/Prometheus/
  Grafana закреплены тегами в prod-overlay.
- [x] `.env.example` содержит только `REQUIRED_*`-плейсхолдеры.
- [x] README раздел «Переменные окружения и секреты», команда
  `openssl rand -base64 32`, упоминание gitleaks-action.
- [x] `docker-compose.prod.yml` поднимает `swipe_consumer` и `match_consumer`
  как отдельные сервисы с `healthcheck: pgrep -f …` и `restart: always`.
- [x] `git ls-files | rg '\.venv|\.log$|__pycache__|\.pyc$'` — пусто,
  tracked-мусора нет.

### Частично выполнено — расхождений с tracking-fix.md нет

- [~] **3.2.1** — формат теста (Locust вместо JMeter): подтверждения PM в
  репозитории нет. Tracking-fix честно ставит 🟡.
- [~] **3.2.5** — отчёт по нагрузке заполнен (включая stress p95-bottleneck),
  но **скриншот Grafana отсутствует** (`docs/stages/stage4_loadtest.md:153`
  ссылается на CSV-историю, PNG не приложен). 🟡 совпадает.
- [~] **3.3.5** — `swipe_consumer`/`match_consumer` объявлены только в
  prod-overlay (`docker-compose.prod.yml`), стендового runtime-прогона
  `docker compose ps/logs` в текущей сессии не зафиксировано. 🟡 совпадает.
- [~] **3.6.3** — раздел отчёта обновлён, но `docs/stages/stage4_report.md`
  в шапке всё ещё помечен «🟡 в работе» и аудит A.1–A.4 у него «⏳» — это
  немного отстаёт от факта, что A.1 уже закрыт. Косметика, не блокер.
- [~] **3.10.1 / 3.10.2** — `logger.bind(...)` встречается лишь 16 раз во
  всём backend+bot; большая часть API-хендлеров (`matching.py`,
  `photos.py`, `profile.py`) всё ещё пишет через f-string без
  контекстных ключей. 🟡 совпадает с tracking-fix.

### В очереди — текущим аудитом закрывается только A.2/А.1

- [?] **A.2** «Повторный аудит после функциональных фиксов» — артефакт ожидался
  под именем `audit-round-3.md`. Этим документом он создаётся.
- [?] **A.3** «Финальный аудит» (`audit-final.md`) — не выполнен, ждёт
  стендового prod-прогона + скриншот Grafana.
- [?] **A.4** «Таблица «требование → балл до/после»» — добавлена в раздел 4
  настоящего документа как предварительная, окончательная — в A.3.

### Требования из `req.md` — где стоим сейчас

| # | Пункт req.md | До (plan-fix.md) | После (фактически) |
|---|---|---:|---:|
| 1 | Рейтинг (3 уровня) | 3 | 3 |
| 2 | Redis (сессии + sorted set + counters) | 2 | 2 |
| 3 | Celery (точечный пересчёт + photo + push) | 1 | 2 |
| 4 | RabbitMQ (publisher + consumer + DLQ) | 1 | 2 |
| 5 | Метрики и логирование | 1 | 2 |
| 6 | S3 (MinIO singleton + thumbnail) | 2 | 2 |
| 7 | CI/CD | 0 | 1 |
| 9 | Этап 1 (планирование) | 3 | 3 |
| 9 | Этап 2 (базовый функционал) | 3 | 3 |
| 9 | Этап 3 (анкеты+рейтинг) | 3 | 3 |
| 9 | БД (схема из этапа 1) | 3 | 3 |
| 9 | Бот работает | 2 | 2 |
| 9 | Нагрузочное тестирование | 0 | 1 |
| **Итого** | | **24** | **29** |

До оценки «5» (30+) остаётся +1 балл. Реалистичный путь: явно засчитать
существующий notification-flow (RabbitMQ `match_notifications` →
`bot/workers/match_consumer.py` → Telegram push) как доп. этап
«сервис notification» из пункта 9 — это требует подтверждения PM,
не дополнительного кода.

---

## 3. Найденные несоответствия

### 3.1 Изменения существуют, но не закоммичены — CI бейдж пустой

- Требование: пункт 7 системы оценивания.
- Текущее состояние: `git status` показывает, что **все ключевые правки**
  (`.github/workflows/ci.yml`, `backend/workers/*`, `backend/tasks/*`,
  `bot/workers/*`, `bot/metrics.py`, `docker-compose.prod.yml`, обновлённый
  README/.env.example/grafana dashboard) находятся в untracked/modified
  состоянии. Последний коммит — `d704458 4 этап`, и в нём этих файлов нет.
- Где обнаружено: `git status --short`.
- Что нужно сделать: после правки замечаний выполнить commit + push в
  ветку `stage4`, убедиться что бейдж `CI` в README действительно стал
  зелёным на удалённом репозитории.
- Приоритет: **высокий** (без push CI-балл не подтверждён формально).

### 3.2 README ссылается на репозиторий третьей стороны

- Текущее состояние: `README.md:3` —
  `https://github.com/DTYUI1/botDateWithLoveLoveLove/actions/workflows/ci.yml`.
  Это репозиторий **не текущего пользователя** (`artwox`), что подозрительно
  для академического проекта.
- Где обнаружено: `README.md:3`.
- Что нужно сделать: проверить, что URL ведёт на правильный репозиторий
  (или заменить на `artwox/connectme` после push). Иначе бейдж бесполезен
  для защиты.
- Приоритет: средний.

### 3.3 README устаревший указатель на отчёт этапа 1

- Текущее состояние: `README.md:77` — «См. stage1_report.md», а фактический
  путь `docs/stages/stage1_report.md`.
- Где обнаружено: `README.md:77,105-107`.
- Что нужно сделать: поправить относительные ссылки на корректные пути.
- Приоритет: низкий.

### 3.4 Скриншот Grafana не приложен к отчёту нагрузки

- Требование: блок 3.2 plan-fix.md — «Отчёт с графиками».
- Текущее состояние: `docs/stages/stage4_loadtest.md:153-154` ссылается на
  `*_stats_history.csv`, но реального PNG/SVG-снимка дашборда в репо нет.
- Что нужно сделать: при следующем прогоне сделать скриншот и положить в
  `docs/stages/img/stage4_load_grafana.png`, обновить отчёт.
- Приоритет: средний (для защиты — важный визуал).

### 3.5 Stage4 report не отражает закрытие A.1

- Текущее состояние: `docs/stages/stage4_report.md:30` помечает аудит
  A.1–A.4 как ⏳, хотя A.1 фактически выполнен (в самом
  `tracking-fix.md:202` стоит ✅).
- Что нужно сделать: обновить статусную таблицу stage4_report.md.
- Приоритет: низкий.

### 3.6 Stage4 report статус «🟡 в работе»

- Текущее состояние: после закрытия A.2 текущим документом статус можно
  поднять до «✅ готов к финальному аудиту».
- Приоритет: низкий.

### 3.7 Адопция контекстного логирования неполная

- Требование: блок 3.10 plan-fix.md.
- Текущее состояние: `logger.bind(...)` встречается лишь 16 раз; в
  `backend/api/v1/matching.py`, `photos.py`, `profile.py` сохраняются
  generic-сообщения вида `f"[Backend Matching] ... telegram_id={...}"`.
  Patcher и helpers (`backend/core/logging_context.py`) есть, но не
  применяются на горячем пути.
- Что нужно сделать: пройтись по API-хендлерам и заменить f-string на
  `bind_user(telegram_id=...)` / `bind_match(...)` из
  `core/logging_context.py`. Это закроет 3.10.1 и 3.10.2 формально.
- Приоритет: низкий.

### 3.8 Endpoint-focused нагрузочный профиль не выполнен

- Текущее состояние: SLA-цель «≥ 50 RPS на endpoint» в
  `docs/stages/stage4_loadtest.md:30` не подтверждена ни одним прогоном
  (full дает 28 RPS/endpoint, stress — 40 RPS/endpoint, оба ниже цели).
- Что нужно сделать: либо снять/смягчить эту SLA-строку, либо запустить
  специально настроенный профиль без `wait_time` и с целевым RPS на
  `/matching/next` и `/matching/swipe`.
- Приоритет: средний (если SLA из ТЗ — нужно подтянуть; если внутренняя
  цель — можно скорректировать в отчёте).

### 3.9 Prod consumer-сервисы не прогнаны на стенде

- Требование: блок 3.3.5 tracking-fix.md.
- Текущее состояние: `swipe_consumer`/`match_consumer` описаны в prod
  overlay, но команды `docker compose -f docker-compose.yml -f
  docker-compose.prod.yml up -d swipe_consumer match_consumer` и
  `docker compose ps`/`logs` не зафиксированы.
- Что нужно сделать: один раз прогнать prod-стек, приложить вывод
  `docker compose ps` + кусок логов, где видно `[Consumer:…] подключён`
  и обработка тестового сообщения. Этого достаточно для закрытия 3.3.5.
- Приоритет: средний.

### 3.10 Артефактные `__pycache__` и `.venv` лежат на диске

- Текущее состояние: `git ls-files` чистый, но в рабочей директории
  `__pycache__/`, `.venv/`, `tests/load/__pycache__/` создают шум при
  `git status`. Сам `.gitignore` их уже покрывает, поэтому риска коммита
  нет.
- Что нужно сделать: ничего обязательного. Опционально — `find . -name
  __pycache__ -exec rm -rf {} +` перед демо.
- Приоритет: косметический.

---

## 4. План фикса (минимальный путь к финальному аудиту)

### Шаг 1. Закоммитить и запушить изменения

```bash
git add -A
git commit -m "stage4: consumer'ы, бизнес-метрики, нагрузочные артефакты, CI"
git push origin stage4
```

Подтвердить, что GitHub Actions отработал зелёным.

### Шаг 2. Поправить README-ссылки

- Проверить URL CI-бейджа и поменять на правильный репозиторий, если
  `DTYUI1/botDateWithLoveLoveLove` — чужой.
- Поправить относительные пути к `stage1_report.md` (раздел «Архитектура»,
  «Документация»).

### Шаг 3. Снять скриншот Grafana

Поднять compose-стек, запустить full SLA-прогон Locust, во время прогона
сохранить дашборд `connectme-backend` в `docs/stages/img/stage4_load_grafana.png`,
дополнить `docs/stages/stage4_loadtest.md` ссылкой.

### Шаг 4. Прогнать prod consumer-сервисы

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d \
    rabbitmq swipe_consumer match_consumer
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 swipe_consumer match_consumer
```

Сохранить лог в `docs/stages/stage4_consumer_run.md` (или приложить к
stage4_report).

### Шаг 5. Подтянуть бизнес-логи

Минимум — заменить 6–8 ключевых `logger.info(f"...{telegram_id}...")` в
`backend/api/v1/matching.py`, `photos.py`, `profile.py` на
`bind_user(telegram_id=...).info(...)`. То же — для bot handlers
(`bot/handlers/search.py`, `start.py`).

### Шаг 6. Обновить статусные документы

- `docs/stages/stage4_report.md` — заменить `🟡 в работе` на `✅` и снять ⏳
  у A.1 в таблице.
- `tracking-fix.md` — отметить A.2 как ✅ со ссылкой на этот файл.

### Шаг 7. Финальный аудит (`audit-final.md`)

После шагов 1–6 — отдельный проход аудитором, который зафиксирует балл
по `req.md` (целевой 27–29 → 30+ при засчёте notification-сервиса) и
закроет A.3/A.4.

---

## 5. Риски и уточнения

- **Конфликт ветки и GitHub Actions:** изменения не закоммичены — все
  заявления «CI зелёный» проверены только локально (`ruff` + `pytest`),
  а realtime-статус GitHub Actions не подтверждён. До push раздел 3.1
  плана `req.md` нельзя считать закрытым «формально».
- **Согласование формата нагрузки с PM:** в репозитории нет ни одного
  артефакта, подтверждающего, что Locust согласован как замена JMeter
  (нет письма, нет коммита PM). Если преподаватель строг — это риск
  снижения балла за пункт 9.
- **Цель «≥ 50 RPS на endpoint»** в `stage4_loadtest.md` сформулирована
  внутри проекта и фактически не достигнута ни в одном прогоне (28/40
  RPS на endpoint). Нужно либо переписать SLA, либо запустить
  endpoint-focused профиль.
- **Бот в проде:** `tracking_table.md` и stage1–3 отчёты говорят, что бот
  работает, но в текущей сессии живой ручной прогон бота не
  выполнялся — только runtime backend/`/metrics`. Перед защитой полезно
  пройти golden path (start → profile → search → swipe → match push).
- **README со ссылкой на сторонний репозиторий** (`DTYUI1/...`) — если
  это случайность, нужно поправить; если намеренный fork — добавить
  README-секцию «происхождение проекта».
- **Notification-сервис:** для оценки «5» осталось формально засчитать
  существующий push-pipeline (RabbitMQ `match_notifications` → bot
  consumer → Telegram push) как «дополнительный этап». Это решается на
  стороне PM, а не кода.

---

*Документ создан в рамках задачи A.2 из `tracking-fix.md`.
Следующий артефакт — `audit-final.md` после выполнения шагов 1–6.*
