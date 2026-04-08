# Тесты для ConnectMe

Эта папка содержит тесты для инфраструктуры и сервисов проекта ConnectMe.

## Структура

```
test/
├── infrastructure/       # Тесты здоровья инфраструктуры
│   └── test_health_check.py
├── services/             # Тесты бизнес-логики
│   └── test_rating_service.py
├── redis/                # Тесты Redis кэширования
│   └── test_redis_cache.py
├── rabbitmq/             # Тесты RabbitMQ publisher
│   └── test_rabbitmq_publisher.py
├── pytest.ini            # Конфигурация pytest
└── requirements.txt      # Test dependencies
```

## Запуск тестов

### Все тесты

```bash
cd test
pytest -v
```

### Только тесты рейтинга (не требуют Docker)

```bash
cd test
pytest services/test_rating_service.py -v
```

### Только тесты Redis (требует Redis)

```bash
cd test
pytest redis/test_redis_cache.py -v
```

### Только тесты RabbitMQ (требует RabbitMQ)

```bash
cd test
pytest rabbitmq/test_rabbitmq_publisher.py -v
```

### Только тесты здоровья (требуют все сервисы)

```bash
cd test
pytest infrastructure/test_health_check.py -v
```

## Зависимости

```bash
pip install -r requirements.txt
```

Или из корня проекта:

```bash
./scripts/run-tests.sh
```

## Результаты

### ✅ Пройдено (24/24 теста)

- **PrimaryRatingCalculator**: 7/7 тестов
  - Заполненность профиля
  - Количество фото
  - Верификация
  - Полный расчёт

- **BehavioralRatingCalculator**: 9/9 тестов
  - Количество лайков
  - Соотношение лайков/пропусков
  - Частота мэтчей
  - Паттерны активности
  - Полный расчёт

- **CombinedRatingCalculator**: 8/8 тестов
  - Высокие/низкие score
  - Назначение tier'ов (S, A, B, C, D, E)
  - Расчёт перцентиля
  - Проверка весов

## Требования к инфраструктуре

Некоторые тесты требуют запущенные сервисы:

| Тест | PostgreSQL | Redis | RabbitMQ | MinIO |
|------|-----------|-------|----------|-------|
| `test_rating_service.py` | ❌ | ❌ | ❌ | ❌ |
| `test_redis_cache.py` | ❌ | ✅ | ❌ | ❌ |
| `test_rabbitmq_publisher.py` | ❌ | ❌ | ✅ | ❌ |
| `test_health_check.py` | ✅ | ✅ | ✅ | ❌ |

**Легенда:** ✅ = требуется, ❌ = не требуется

## Запуск инфраструктуры

```bash
# Из корня проекта
./scripts/setup-infra.sh

# Проверить здоровье
./scripts/health-check.sh
```

## CI/CD

Тесты можно запускать в CI/CD пайплайне:

```yaml
# Пример для GitHub Actions
- name: Run tests
  run: |
    cd test
    pip install -r requirements.txt
    pytest services/test_rating_service.py -v
```
