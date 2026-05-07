-- Dirty read: чтение неподтвержденных данных.
-- Перед сценарием выполните sql/00_schema.sql.

-- SESSION A
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
UPDATE accounts SET balance = 50 WHERE id = 1;
-- Не выполняйте COMMIT/ROLLBACK до шага SESSION B.

-- SESSION B
SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
START TRANSACTION;
SELECT balance AS dirty_balance FROM accounts WHERE id = 1;
-- Ожидаемый результат: 50, хотя SESSION A еще не сделала COMMIT.

-- SESSION A
ROLLBACK;

-- SESSION B
SELECT balance AS balance_after_rollback FROM accounts WHERE id = 1;
-- Ожидаемый результат: 100. Значение 50 оказалось грязным чтением.
COMMIT;
