# Как показать решение преподавателю

## Вариант 1 — Показать прямо в терминале (минимум действий)

```bash
# 1. Перейти в папку проекта
cd ~/orchestrAI/loveBot/projects/connectme/practice/p1

# 2. Запустить — приложение само отработает и завершится
docker compose up --build --abort-on-container-exit 

# 3. Поднять только БД
docker compose up -d db

# 4. Выполнить SELECT'ы
docker compose exec db psql -U user -d store -c "
SELECT * FROM customers;
SELECT * FROM products;
SELECT * FROM orders;
SELECT * FROM orderitems;
"

# 5. После показа — остановить всё
docker compose down
```

---

## Вариант 2 — Показать через pgAdmin (визуально, в браузере)

Добавить в `docker-compose.yml` сервис pgAdmin:

```yaml
  pgadmin:
    image: dpage/pgadmin4
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@admin.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - db
```

Затем:
```bash
docker compose up --build --abort-on-container-exit
docker compose up -d db pgadmin
```

Открыть браузер: `http://localhost:5050`
- Логин: `admin@admin.com` / `admin`
- Подключиться к серверу: хост `db`, порт `5432`, пользователь `user`, пароль `password`, база `store`
- Открыть таблицы через дерево слева → кликнуть правой кнопкой → **View/Edit Data → All Rows**

---

**Рекомендация:** для преподавателя Вариант 1 проще и быстрее — всё в одном терминале, хорошо читается.
