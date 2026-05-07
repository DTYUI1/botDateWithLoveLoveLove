-- Non-repeatable read: повторное чтение той же строки дает другой результат.
-- Перед сценарием выполните sql/00_schema.sql.

-- SESSION A
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT price AS first_price FROM products WHERE id = 1;
-- Ожидаемый результат: 100.

-- SESSION B
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
UPDATE products SET price = 120 WHERE id = 1;
COMMIT;

-- SESSION A
SELECT price AS second_price FROM products WHERE id = 1;
-- Ожидаемый результат: 120 в той же транзакции SESSION A.
COMMIT;
