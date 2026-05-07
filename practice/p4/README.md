# Практика: аномалии изоляции в SQL

Проект показывает четыре аномалии изоляции на MySQL/InnoDB:

- `dirty read`;
- `non-repeatable read`;
- `phantom read`;
- `lost update`.

## Быстрый запуск

1. Запустить MySQL:

```bash
docker compose up -d mysql
```

2. Установить зависимость для Python-раннера:

```bash
python3 -m pip install -r requirements.txt
```

3. Запустить автоматическое воспроизведение:

```bash
python3 scripts/run_anomalies.py
```

Скрипт выведет лог в консоль и сохранит его в `report/run_log.txt`.

Если MySQL уже установлен без Docker, задайте параметры подключения через переменные окружения:

```bash
DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=root DB_PASSWORD=root DB_NAME=isolation_lab \
python3 scripts/run_anomalies.py
```

## Ручная проверка

Сначала выполните `sql/00_schema.sql`, затем откройте две SQL-сессии к одной базе `isolation_lab`.
Дальше выполняйте шаги из файлов:

- `sql/01_dirty_read.sql`;
- `sql/02_non_repeatable_read.sql`;
- `sql/03_phantom_read.sql`;
- `sql/04_lost_update.sql`.

Отчет для сдачи находится в `report/report.md`.
