-- Lost update: два клиента читают одно значение и записывают результат,
-- рассчитанный на стороне приложения. Одно увеличение теряется.
-- Перед сценарием выполните sql/00_schema.sql.

-- SESSION A
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT value AS value_for_session_a FROM counters WHERE id = 1;
-- Ожидаемый результат: 10. Приложение SESSION A вычисляет 10 + 1 = 11.

-- SESSION B
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT value AS value_for_session_b FROM counters WHERE id = 1;
-- Ожидаемый результат: 10. Приложение SESSION B вычисляет 10 + 1 = 11.

-- SESSION A
UPDATE counters SET value = 11 WHERE id = 1;
COMMIT;

-- SESSION B
UPDATE counters SET value = 11 WHERE id = 1;
COMMIT;

-- Любая сессия
SELECT value AS final_value FROM counters WHERE id = 1;
-- Ожидаемый результат: 11 вместо корректного 12.
