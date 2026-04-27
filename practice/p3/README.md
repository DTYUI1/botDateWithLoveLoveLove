# p3 — Сравнение типов кеширования

Одна и та же система с тремя стратегиями работы с кешем:

- **Cache-Aside** (Lazy Loading / Write-Around) — `app/strategies/cache_aside.py`
- **Write-Through** — `app/strategies/write_through.py`
- **Write-Back** — `app/strategies/write_back.py`

Стек: FastAPI + SQLAlchemy(async) + asyncpg + redis.asyncio. БД — PostgreSQL 16, кеш — Redis 7. Нагрузочный генератор — самописный на `asyncio + httpx`.

## Что внутри

```
app/                FastAPI приложение, общие БД/кеш модули, три стратегии
loadgen/            нагрузочный генератор (Zipf по ключам, три профиля)
scripts/run_all.sh  прогон всех 3 стратегий × 3 профилей подряд
docker-compose.yml  postgres + redis + app + loadgen
report.md           итоговый отчёт с таблицами и выводами
results/            CSV-результаты и скрины консоли
```

## Запуск

Требования: Docker и `docker compose` v2.

```bash
# единичный прогон одной стратегии и всех 3 профилей
CACHE_STRATEGY=cache_aside docker compose up -d --force-recreate app
docker compose run --rm loadgen --strategy cache_aside

# полный прогон 3×3 (рекомендуется)
bash scripts/run_all.sh
```

Артефакты после прогона:

- `results/summary.csv` — сводная таблица 9 строк (3 стратегии × 3 профиля).
- `results/latencies_<strategy>_<profile>.csv` — все измерения латентности.
- `results/wb_timeline_*.csv` — динамика очереди Write-Back во времени.
- `results/screenshots/` — скрины консоли для отчёта.

## Параметры теста (по умолчанию)

| Параметр | Значение | Где меняется |
|---|---|---|
| Длительность | 60 сек | `DURATION` |
| Параллельных клиентов | 100 | `CONCURRENCY` |
| Размер ключевого пространства | 10 000 | `N_KEYS` / `SEED_ITEMS` |
| Распределение ключей | Zipf, α=1.2 | `ZIPF_ALPHA` |
| Профили | 80/20, 50/50, 20/80 | `loadgen/workload.py` |
| WB-flush интервал / batch | 1 сек / 500 | `WB_FLUSH_INTERVAL`, `WB_FLUSH_BATCH` |

## Метрики

| Что | Где считается |
|---|---|
| `throughput` (rps) | loadgen, `requests_total / duration` |
| `avg / p50 / p95 / p99 latency` | loadgen, локальные measurements |
| Обращения к БД | `app/db.py` инкрементирует `db_reads`/`db_writes` в каждом запросе к Postgres |
| Hit rate кеша | `app/cache.py` инкрементирует `cache_hits/cache_misses`; для контроля сверяется с `INFO stats` Redis (`keyspace_hits/misses`) |
| Write-Back при накоплении | `wb_queue_size`, `wb_flushes`, `wb_flushed_rows` + таймлайн в `results/wb_timeline_*.csv` |

## Демо

См. `how_to_demo.md` — короткий чек-лист для показа преподавателю.
