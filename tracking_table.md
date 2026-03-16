# 📊 Таблица отслеживания задач

**Проект:** ConnectMe — Dating-бот с функцией «Ледокол»  
**Дата начала:** 2026-03-16  
**Git-репозиторий:** git@github.com:DTYUI1/botDateWithLoveLoveLove.git

---

## Этап 1: Планирование и проектирование ✅

| № | Задача | Исполнитель | Статус | Дата | Артефакт |
|---|--------|-------------|--------|------|----------|
| 1.1 | Сбор требований | Product Manager | ✅ | 2026-03-16 | prd.json |
| 1.2 | Проектирование архитектуры | System Architect | ✅ | 2026-03-16 | architecture.md, services.md |
| 1.3 | Создание схемы БД | Database Designer | ✅ | 2026-03-16 | database_schema.md, dbdiagram.dbml |
| 1.4 | Создание сводного отчёта | Technical Writer | ✅ | 2026-03-16 | stage1_report.md |
| 1.5 | Настройка Git-репозитория | DevOps Engineer | ✅ | 2026-03-16 | docker-compose.yml, .env.example, README.md |

---

## Этап 2: Разработка базовой функциональности ⬜

| № | Задача | Исполнитель | Статус | Дата | Артефакт |
|---|--------|-------------|--------|------|----------|
| 2.1 | Написание Telegram Bot | Telegram Bot Developer | ⬜ | — | bot/ |
| 2.2 | Реализация регистрации (/start) | Telegram Bot Developer | ⬜ | — | handlers/start.py |
| 2.3 | Создание анкеты (FSM) | Telegram Bot Developer | ⬜ | — | handlers/profile.py |
| 2.4 | Backend API (CRUD профилей) | Backend Developer | ⬜ | — | api/v1/profile.py |

---

## Этап 3: Система анкет и ранжирования ⬜

| № | Задача | Исполнитель | Статус | Дата | Артефакт |
|---|--------|-------------|--------|------|----------|
| 3.1 | CRUD для анкет | Backend Developer | ⬜ | — | services/profile_service.py |
| 3.2 | Алгоритм ранжирования (Уровень 1) | Backend Developer | ⬜ | — | services/rating_service.py |
| 3.3 | Алгоритм ранжирования (Уровень 2) | Backend Developer | ⬜ | — | services/rating_service.py |
| 3.4 | Алгоритм ранжирования (Уровень 3) | Backend Developer | ⬜ | — | services/rating_service.py |
| 3.5 | Кэширование в Redis (10 анкет) | Queue/Cache Engineer | ⬜ | — | redis/session_cache.py |
| 3.6 | Интеграция с ботом | Telegram Bot Developer | ⬜ | — | handlers/search.py |

---

## Этап 4: Дополнительные функции ⬜

| № | Задача | Исполнитель | Статус | Дата | Артефакт |
|---|--------|-------------|--------|------|----------|
| 4.1 | Настройка Celery (пересчёт рейтингов) | Backend Developer | ⬜ | — | celery_app.py |
| 4.2 | Оптимизация БД (индексы) | Database Designer | ⬜ | — | database/indexes.sql |
| 4.3 | Функция «Ледокол» | Telegram Bot Developer | ⬜ | — | handlers/icebreaker.py |
| 4.4 | Идеи для свиданий | Backend Developer | ⬜ | — | api/v1/date_ideas.py |
| 4.5 | Тестирование | QA Engineer | ⬜ | — | tests/ |
| 4.6 | Деплой на сервер | DevOps Engineer | ⬜ | — | docker-compose.prod.yml |

---

## Сводка по проекту

| Метрика | Значение |
|---------|----------|
| Всего задач | 21 |
| Выполнено | 5 |
| В работе | 0 |
| Ожидает | 16 |
| Прогресс | **23.8%** |

---

## 🎯 Критерии приёмки Этапа 1

- [x] PRD создан и утверждён
- [x] Архитектура спроектирована (Mermaid-диаграмма)
- [x] Схема БД создана (DBML для dbdiagram.io)
- [x] Сводный отчёт подготовлен (stage1_report.md)
- [x] Git-репозиторий настроен
- [x] Docker Compose конфигурация создана

---

*Таблица создана автономной системой loveBot для отслеживания прогресса проекта ConnectMe.*
