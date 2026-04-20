# Как показать решение преподавателю

## Вариант 1 — Запуск в терминале (минимум действий)

```bash
# 1. Перейти в папку проекта
cd ~/orchestrAI/loveBot/projects/connectme/practice/p2

# 2. Запустить всю матрицу (≈12 минут)
docker compose up --build --abort-on-container-exit

# 3. После завершения посмотреть CSV с результатами
cat results/results.csv

# 4. Остановить и убрать volumes
docker compose down -v
```

В stdout в конце выводится итоговая таблица (`broker | size | rate | sent | recv | lost% | thr | avg | p95 | cpu | mem | status`) и секция «ВЫВОДЫ» с автоматически подсвеченными точками деградации.

## Вариант 2 — С живым просмотром в RabbitMQ UI

Во время прогона (пока идут 12 RabbitMQ-прогонов — это первая половина матрицы) открыть:

```
http://localhost:15673
```

Логин: `guest` / пароль: `guest`
→ вкладка **Queues** → `bench_q` → видны графики Incoming / Deliver / Ack и глубина очереди.

## Вариант 3 — Быстрый smoke (1.5 минуты, для отладки)

В `docker-compose.yml` временно подменить env-переменные bench:

```yaml
BENCH_DURATION: "5"
BENCH_SIZES: "1024"
BENCH_RATES: "1000,5000"
```

Итого 4 прогона × 5 секунд — хватает убедиться, что стенд жив.

## Файлы с результатами

- `results/results.csv` — итоговая таблица со всеми метриками по каждому прогону.
- `results/stats_<broker>_<size>_<rate>.csv` — посекундные CPU/RAM брокера.

---

**Рекомендация:** Вариант 1 — простой, одно окно терминала, всё наглядно. Для защиты добавить скрин RabbitMQ UI из Варианта 2.
