from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "sql" / "00_schema.sql"
LOG_PATH = ROOT / "report" / "run_log.txt"


def db_name() -> str:
    return os.getenv("DB_NAME", "isolation_lab")


def connect(database: str | None = None) -> pymysql.connections.Connection:
    selected_database = db_name() if database is None else database
    kwargs: dict[str, Any] = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "root"),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": pymysql.cursors.DictCursor,
    }
    if selected_database:
        kwargs["database"] = selected_database
    return pymysql.connect(**kwargs)


class Logger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message: str = "") -> None:
        print(message)
        self.lines.append(message)

    def save(self) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def execute_script(conn: pymysql.connections.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()


def scalar(conn: pymysql.connections.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return next(iter(row.values()))


def exec_sql(conn: pymysql.connections.Connection, sql: str, params: tuple[Any, ...] = ()) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params)


def begin(conn: pymysql.connections.Connection, isolation_level: str) -> None:
    exec_sql(conn, f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
    exec_sql(conn, "START TRANSACTION")


def reset_schema(log: Logger) -> None:
    with connect() as conn:
        execute_script(conn, SCHEMA_SQL)
    log.write("Схема и тестовые данные сброшены.")


def ensure_database() -> None:
    name = db_name().replace("`", "``")
    with connect(database="") as conn:
        exec_sql(conn, f"CREATE DATABASE IF NOT EXISTS `{name}`")
        conn.commit()


# 1. DIRTY READ
# Транзакция B читает изменение транзакции A до COMMIT, затем A делает ROLLBACK.
def dirty_read(log: Logger) -> None:
    log.write("\n== DIRTY READ ==")
    reset_schema(log)
    a = connect()
    b = connect()
    try:
        begin(a, "READ COMMITTED")
        exec_sql(a, "UPDATE accounts SET balance = 50 WHERE id = 1")
        log.write("A: UPDATE accounts SET balance = 50, COMMIT еще не выполнен.")

        begin(b, "READ UNCOMMITTED")
        dirty_balance = scalar(b, "SELECT balance FROM accounts WHERE id = 1")
        log.write(f"B: SELECT balance -> {dirty_balance}")

        a.rollback()
        log.write("A: ROLLBACK")

        balance_after_rollback = scalar(b, "SELECT balance FROM accounts WHERE id = 1")
        b.commit()
        log.write(f"B: повторный SELECT balance -> {balance_after_rollback}")
        log.write("Результат: B прочитала 50, хотя после ROLLBACK в таблице снова 100.")
    finally:
        a.close()
        b.close()


# 2. NON-REPEATABLE READ
# Транзакция A дважды читает одну строку, а между чтениями B меняет ее и делает COMMIT.
def non_repeatable_read(log: Logger) -> None:
    log.write("\n== NON-REPEATABLE READ ==")
    reset_schema(log)
    a = connect()
    b = connect()
    try:
        begin(a, "READ COMMITTED")
        first_price = scalar(a, "SELECT price FROM products WHERE id = 1")
        log.write(f"A: первый SELECT price -> {first_price}")

        begin(b, "READ COMMITTED")
        exec_sql(b, "UPDATE products SET price = 120 WHERE id = 1")
        b.commit()
        log.write("B: UPDATE price = 120; COMMIT")

        second_price = scalar(a, "SELECT price FROM products WHERE id = 1")
        a.commit()
        log.write(f"A: второй SELECT price в той же транзакции -> {second_price}")
        log.write("Результат: одна и та же строка изменилась с 100 на 120.")
    finally:
        a.close()
        b.close()


# 3. PHANTOM READ
# Транзакция A дважды выполняет запрос по условию, а между чтениями B вставляет новую строку.
def phantom_read(log: Logger) -> None:
    log.write("\n== PHANTOM READ ==")
    reset_schema(log)
    a = connect()
    b = connect()
    try:
        begin(a, "READ COMMITTED")
        first_count = scalar(a, "SELECT COUNT(*) FROM orders_demo WHERE status = 'NEW'")
        log.write(f"A: первый COUNT(status='NEW') -> {first_count}")

        begin(b, "READ COMMITTED")
        exec_sql(
            b,
            "INSERT INTO orders_demo (customer_name, status, amount) VALUES (%s, %s, %s)",
            ("Petr", "NEW", 700),
        )
        b.commit()
        log.write("B: INSERT нового заказа со status='NEW'; COMMIT")

        second_count = scalar(a, "SELECT COUNT(*) FROM orders_demo WHERE status = 'NEW'")
        a.commit()
        log.write(f"A: второй COUNT(status='NEW') в той же транзакции -> {second_count}")
        log.write("Результат: появился фантомный заказ, счетчик изменился с 1 на 2.")
    finally:
        a.close()
        b.close()


# 4. LOST UPDATE
# Две транзакции читают одно значение, независимо вычисляют новое и записывают его обратно.
def lost_update(log: Logger) -> None:
    log.write("\n== LOST UPDATE ==")
    reset_schema(log)
    a = connect()
    b = connect()
    try:
        begin(a, "READ COMMITTED")
        value_a = scalar(a, "SELECT value FROM counters WHERE id = 1")
        log.write(f"A: SELECT value -> {value_a}; приложение вычисляет {value_a} + 1 = {value_a + 1}")

        begin(b, "READ COMMITTED")
        value_b = scalar(b, "SELECT value FROM counters WHERE id = 1")
        log.write(f"B: SELECT value -> {value_b}; приложение вычисляет {value_b} + 1 = {value_b + 1}")

        exec_sql(a, "UPDATE counters SET value = %s WHERE id = 1", (value_a + 1,))
        a.commit()
        log.write("A: UPDATE counters SET value = 11; COMMIT")

        exec_sql(b, "UPDATE counters SET value = %s WHERE id = 1", (value_b + 1,))
        b.commit()
        log.write("B: UPDATE counters SET value = 11; COMMIT")

        with connect() as check:
            final_value = scalar(check, "SELECT value FROM counters WHERE id = 1")
        log.write(f"Итоговое значение -> {final_value}")
        log.write("Результат: ожидалось 12, но одно обновление потеряно, в таблице 11.")
    finally:
        a.close()
        b.close()


def main() -> None:
    log = Logger()
    log.write(f"Запуск: {datetime.now().isoformat(timespec='seconds')}")
    ensure_database()
    dirty_read(log)
    non_repeatable_read(log)
    phantom_read(log)
    lost_update(log)
    log.save()
    log.write(f"\nЛог сохранен в {LOG_PATH}")


if __name__ == "__main__":
    main()
