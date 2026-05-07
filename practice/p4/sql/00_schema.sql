DROP TABLE IF EXISTS orders_demo;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS counters;
DROP TABLE IF EXISTS accounts;

CREATE TABLE accounts (
    id INT PRIMARY KEY,
    owner_name VARCHAR(50) NOT NULL,
    balance INT NOT NULL
) ENGINE = InnoDB;

CREATE TABLE products (
    id INT PRIMARY KEY,
    title VARCHAR(50) NOT NULL,
    price INT NOT NULL
) ENGINE = InnoDB;

CREATE TABLE orders_demo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    amount INT NOT NULL,
    INDEX idx_orders_status (status)
) ENGINE = InnoDB;

CREATE TABLE counters (
    id INT PRIMARY KEY,
    value INT NOT NULL
) ENGINE = InnoDB;

INSERT INTO accounts (id, owner_name, balance) VALUES
    (1, 'Alice', 100);

INSERT INTO products (id, title, price) VALUES
    (1, 'Keyboard', 100);

INSERT INTO orders_demo (customer_name, status, amount) VALUES
    ('Ivan', 'NEW', 500),
    ('Olga', 'DONE', 900);

INSERT INTO counters (id, value) VALUES
    (1, 10);
