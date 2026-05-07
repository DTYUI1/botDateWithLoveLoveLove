-- Phantom read: повторный запрос по условию видит новую строку-фантом.
-- Перед сценарием выполните sql/00_schema.sql.

-- SESSION A
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT COUNT(*) AS first_new_orders FROM orders_demo WHERE status = 'NEW';
-- Ожидаемый результат: 1.

-- SESSION B
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
INSERT INTO orders_demo (customer_name, status, amount)
VALUES ('Petr', 'NEW', 700);
COMMIT;

-- SESSION A
SELECT COUNT(*) AS second_new_orders FROM orders_demo WHERE status = 'NEW';
-- Ожидаемый результат: 2 в той же транзакции SESSION A.
COMMIT;
