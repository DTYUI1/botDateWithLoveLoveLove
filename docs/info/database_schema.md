# ConnectMe — Схема базы данных PostgreSQL

**Версия:** 2.0.0
**Дата создания:** 2026-03-16
**Проект:** ConnectMe Dating Bot

---

## Обзор

Схема базы данных разработана для микросервисной системы знакомств ConnectMe с поддержкой:
- Регистрации и управления профилями
- Системы свайпов и мэтчей
- Многоуровневой системы рейтингов (первичный, поведенческий, комбинированный)
- Реферальной программы
- Сессионного управления
- Метрик и аналитики
- **Безопасности** (жалобы, блокировки)
- **Rate limiting** (дневные лимиты)
- **Уведомлений**
- **Аудита действий**

---

## ENUM типы

| Тип | Значения |
|-----|----------|
| `gender_enum` | `male`, `female`, `other` |
| `looking_for_enum` | `male`, `female`, `both` |
| `relationship_goal_enum` | `casual`, `serious`, `friendship`, `networking` |
| `swipe_action_enum` | `like`, `pass`, `super_like` |
| `match_status_enum` | `active`, `archived`, `blocked`, `unmatched` |
| `moderation_status_enum` | `pending`, `approved`, `rejected`, `under_review` |
| `metric_type_enum` | `counter`, `gauge`, `histogram` |
| `date_category_enum` | `cafe`, `activity`, `outdoor`, `cultural`, `entertainment` |
| `cost_level_enum` | `free`, `low`, `medium`, `high` |
| `report_reason_enum` | `spam`, `fake_profile`, `harassment`, `inappropriate_content`, `underage`, `other` |
| `report_status_enum` | `open`, `investigating`, `resolved`, `dismissed` |
| `block_reason_enum` | `manual`, `report`, `system` |

---

## Таблицы

### 1. users

**Описание:** Базовая сущность пользователя Telegram.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| telegram_id | BIGINT | UNIQUE, NOT NULL | ID пользователя в Telegram |
| username | VARCHAR(255) | | Имя пользователя |
| first_name | VARCHAR(255) | NOT NULL | Имя |
| last_name | VARCHAR(255) | | Фамилия |
| language_code | VARCHAR(10) | DEFAULT 'ru' | Язык интерфейса |
| is_banned | BOOLEAN | DEFAULT FALSE | Глобальный бан |
| ban_reason | TEXT | | Причина бана |
| banned_at | TIMESTAMPTZ | | Дата бана |
| last_active_at | TIMESTAMPTZ | | Последняя активность |
| deleted_at | TIMESTAMPTZ | | Soft delete |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата регистрации |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_users_telegram_id` (telegram_id)
- `idx_users_last_active` (last_active_at) WHERE deleted_at IS NULL

---

### 2. profiles

**Описание:** Расширенный профиль пользователя для знакомств.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| user_id | UUID | FK → users(id), UNIQUE, NOT NULL | Ссылка на пользователя |
| display_name | VARCHAR(100) | | Имя для показа |
| date_of_birth | DATE | NOT NULL | Дата рождения |
| gender | gender_enum | NOT NULL | Пол |
| bio | TEXT | | Описание (~1000 символов) |
| height_cm | SMALLINT | | Рост в см |
| interests | JSONB | DEFAULT '[]'::jsonb | Интересы |
| city | VARCHAR(100) | | Город |
| country_code | CHAR(2) | | Страна (ISO 3166-1) |
| latitude | DECIMAL(9,6) | CHECK (-90 до 90) | Широта |
| longitude | DECIMAL(9,6) | CHECK (-180 до 180) | Долгота |
| location_updated_at | TIMESTAMPTZ | | Обновление геоданных |
| looking_for | looking_for_enum | NOT NULL | Кого ищет |
| age_range_min | SMALLINT | DEFAULT 18 | Мин. возраст поиска |
| age_range_max | SMALLINT | DEFAULT 100 | Макс. возраст поиска |
| distance_max_km | SMALLINT | DEFAULT 100 | Макс. расстояние (км) |
| is_active | BOOLEAN | DEFAULT TRUE | Активен ли профиль |
| is_verified | BOOLEAN | DEFAULT FALSE | Верифицирован |
| verified_at | TIMESTAMPTZ | | Дата верификации |
| profile_completion_pct | SMALLINT | DEFAULT 0 | % заполнения (кэш) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_profiles_user_id` (user_id)
- `idx_profiles_active_gender` (gender, is_active)
- `idx_profiles_city` (city) WHERE is_active = true
- `idx_profiles_location` (latitude, longitude) WHERE is_active = true
- `idx_profiles_dob` (date_of_birth)
- `idx_profiles_interests` (interests) USING GIN

---

### 3. preferences

**Описание:** Детальные предпочтения для тонкой настройки подбора.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile_id | UUID | FK → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| preferred_cities | JSONB | DEFAULT '[]'::jsonb | Предпочтительные города |
| preferred_countries | JSONB | DEFAULT '[]'::jsonb | Предпочтительные страны |
| education_preference | VARCHAR(50) | | Предпочтение по образованию |
| occupation_preference | VARCHAR(50) | | Предпочтение по профессии |
| relationship_goals | relationship_goal_enum | | Цель знакомства |
| height_min_cm | SMALLINT | | Мин. рост |
| height_max_cm | SMALLINT | | Макс. рост |
| deal_breakers | JSONB | DEFAULT '[]'::jsonb | Недопустимые качества |
| importance_weights | JSONB | DEFAULT '{"age": 0.2, "distance": 0.3, "interests": 0.5}' | Веса параметров |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

---

### 4. photos

**Описание:** Метаданные фотографий с AI-модерацией.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile_id | UUID | FK → profiles(id), NOT NULL | Ссылка на профиль |
| s3_key | VARCHAR(500) | NOT NULL | Ключ в S3 |
| s3_bucket | VARCHAR(100) | DEFAULT 'profile-photos' | Бакет S3 |
| thumbnail_s3_key | VARCHAR(500) | | Превью |
| blurhash | VARCHAR(50) | | Placeholder |
| is_primary | BOOLEAN | DEFAULT FALSE | Основное фото |
| sort_order | SMALLINT | DEFAULT 0 | Порядок |
| file_size_bytes | INTEGER | | Размер файла |
| mime_type | VARCHAR(50) | DEFAULT 'image/jpeg' | MIME-тип |
| width | SMALLINT | | Ширина (px) |
| height | SMALLINT | | Высота (px) |
| moderation_status | moderation_status_enum | DEFAULT 'pending' | Статус модерации |
| moderated_by | UUID | FK → users(id) | Кто модерировал |
| moderated_at | TIMESTAMPTZ | | Дата модерации |
| rejection_reason | TEXT | | Причина отклонения |
| nsfw_score | DECIMAL(3,2) | | AI-оценка NSFW (0-1) |
| face_detected | BOOLEAN | | Лицо обнаружено |
| deleted_at | TIMESTAMPTZ | | Soft delete |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата загрузки |

**Индексы:**
- `idx_photos_profile` (profile_id, sort_order) WHERE deleted_at IS NULL
- `idx_photos_primary` (profile_id) WHERE is_primary = true AND deleted_at IS NULL

---

### 5. swipes

**Описание:** История действий (лайки/пропуски).

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| swiper_id | UUID | FK → profiles(id), NOT NULL | Кто свайпнул |
| swiped_id | UUID | FK → profiles(id), NOT NULL | Кого свайпнули |
| action | swipe_action_enum | NOT NULL | Действие |
| source | VARCHAR(20) | | Источник (discovery, daily_picks) |
| time_spent_ms | INTEGER | | Время просмотра (мс) |
| context_data | JSONB | DEFAULT '{}'::jsonb | Контекст для ML |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата свайпа |

**Индексы:**
- `idx_swipes_pair` (swiper_id, swiped_id) — UNIQUE
- `idx_swipes_swiped` (swiped_id, action) WHERE action = 'like'
- `idx_swipes_created` (created_at)

---

### 6. matches

**Описание:** Взаимные лайки (мэтчи).

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile1_id | UUID | FK → profiles(id), NOT NULL | Первый профиль |
| profile2_id | UUID | FK → profiles(id), NOT NULL | Второй профиль |
| status | match_status_enum | DEFAULT 'active' | Статус |
| initiator_id | UUID | FK → profiles(id) | Кто начал общение |
| message_count | INTEGER | DEFAULT 0 | Количество сообщений (кэш) |
| last_message_at | TIMESTAMPTZ | | Дата последнего сообщения |
| last_message_preview | VARCHAR(100) | | Превью последнего сообщения |
| unmatched_by | UUID | FK → profiles(id) | Кто размэтчил |
| unmatched_at | TIMESTAMPTZ | | Дата размэтча |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_matches_pair` (profile1_id, profile2_id) — UNIQUE
- `idx_matches_profile1` (profile1_id, status) WHERE status = 'active'
- `idx_matches_profile2` (profile2_id, status) WHERE status = 'active'
- `idx_matches_last_msg` (last_message_at DESC) WHERE status = 'active'

---

### 7. messages

**Описание:** Сообщения в чате между мэтчами.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| match_id | UUID | FK → matches(id), NOT NULL | Ссылка на мэтч |
| sender_id | UUID | FK → profiles(id), NOT NULL | Отправитель |
| content | TEXT | | Текст сообщения |
| message_type | VARCHAR(20) | DEFAULT 'text' | Тип: text, image, voice, gif, sticker |
| media_urls | JSONB | DEFAULT '[]'::jsonb | Ссылки на медиа |
| is_read | BOOLEAN | DEFAULT FALSE | Прочитано |
| read_at | TIMESTAMPTZ | | Дата прочтения |
| is_delivered | BOOLEAN | DEFAULT FALSE | Доставлено |
| delivered_at | TIMESTAMPTZ | | Дата доставки |
| reply_to_id | UUID | FK → messages(id) | Ответ на сообщение |
| is_edited | BOOLEAN | DEFAULT FALSE | Редактировалось |
| edited_at | TIMESTAMPTZ | | Дата редактирования |
| deleted_at | TIMESTAMPTZ | | Soft delete |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата отправки |

**Индексы:**
- `idx_messages_match` (match_id, created_at DESC) WHERE deleted_at IS NULL
- `idx_messages_unread` (match_id, sender_id) WHERE is_read = false AND deleted_at IS NULL

---

### 8. reports

**Описание:** Жалобы пользователей на модерацию.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| reporter_profile_id | UUID | FK → profiles(id), NOT NULL | Кто пожаловался |
| reported_profile_id | UUID | FK → profiles(id), NOT NULL | На кого жалоба |
| reason | report_reason_enum | NOT NULL | Причина |
| description | TEXT | | Описание |
| evidence_urls | JSONB | DEFAULT '[]'::jsonb | Ссылки на доказательства |
| message_id | UUID | FK → messages(id) | Конкретное сообщение |
| status | report_status_enum | DEFAULT 'open' | Статус |
| reviewed_by | UUID | FK → users(id) | Модератор |
| reviewed_at | TIMESTAMPTZ | | Дата проверки |
| resolution_notes | TEXT | | Заметки модератора |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_reports_status` (status) WHERE status IN ('open', 'investigating')
- `idx_reports_reported` (reported_profile_id)

---

### 9. blocks

**Описание:** Блокировки пользователей.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| blocker_profile_id | UUID | FK → profiles(id), NOT NULL | Кто заблокировал |
| blocked_profile_id | UUID | FK → profiles(id), NOT NULL | Кого заблокировали |
| reason | block_reason_enum | DEFAULT 'manual' | Причина |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата блокировки |

**Индексы:**
- `idx_blocks_blocker` (blocker_profile_id)
- `idx_blocks_blocked` (blocked_profile_id)

---

### 10. ratings_primary

**Описание:** Первичный рейтинг на основе данных анкеты.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile_id | UUID | FK → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| completeness_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Полнота анкеты (30%) |
| photo_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Качество фото (30%) |
| photo_count | SMALLINT | DEFAULT 0 | Количество фото |
| preference_match_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Соответствие предпочтениям (20%) |
| verification_bonus | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Бонус за верификацию (20%) |
| total_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Итоговый рейтинг |
| version | INTEGER | DEFAULT 1 | Версия (оптимистичная блокировка) |
| calculated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата расчёта |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_ratings_primary_profile` (profile_id)
- `idx_ratings_primary_score` (total_score DESC)

---

### 11. ratings_behavioral

**Описание:** Поведенческий рейтинг на основе активности.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile_id | UUID | FK → profiles(id), NOT NULL | Ссылка на профиль |
| like_received_count | INTEGER | DEFAULT 0 | Получено лайков |
| pass_received_count | INTEGER | DEFAULT 0 | Получено пропусков |
| like_count_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Рейтинг по лайкам (25%) |
| like_pass_ratio_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Соотношение лайк/пропуск (25%) |
| match_rate_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Частота мэтчей (20%) |
| conversation_initiation_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Инициирование диалогов (15%) |
| response_rate_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Частота ответов (10%) |
| activity_pattern_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Паттерны активности (5%) |
| total_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Итоговый поведенческий рейтинг |
| period_start | DATE | NOT NULL | Начало периода |
| period_end | DATE | NOT NULL | Конец периода |
| calculated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата расчёта |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |

**Индексы:**
- `idx_ratings_beh_profile_period` (profile_id, period_end DESC)

---

### 12. ratings_combined

**Описание:** Комбинированный рейтинг — интеграция всех факторов.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile_id | UUID | FK → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| primary_score | DECIMAL(5,4) | NOT NULL, CHECK (0-1) | Первичный рейтинг |
| primary_weight | DECIMAL(3,2) | DEFAULT 0.40 | Вес первичного |
| behavioral_score | DECIMAL(5,4) | NOT NULL, CHECK (0-1) | Поведенческий рейтинг |
| behavioral_weight | DECIMAL(3,2) | DEFAULT 0.50 | Вес поведенческого |
| referral_bonus | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Реферальный бонус |
| referral_weight | DECIMAL(3,2) | DEFAULT 0.10 | Вес реферального |
| total_score | DECIMAL(5,4) | DEFAULT 0, CHECK (0-1) | Итоговый комбинированный рейтинг |
| rank_position | INTEGER | | Позиция в рейтинге |
| percentile | DECIMAL(5,4) | | Процентиль |
| tier | VARCHAR(10) | | Tier: S/A/B/C/D |
| calculated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата расчёта |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_ratings_combined_profile` (profile_id)
- `idx_ratings_combined_score` (total_score DESC)
- `idx_ratings_combined_tier` (tier)

---

### 13. referrals

**Описание:** Реферальная программа.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| referrer_id | UUID | FK → users(id), NOT NULL | Кто пригласил |
| referred_id | UUID | FK → users(id), UNIQUE, NOT NULL | Кого пригласили |
| referral_code | VARCHAR(50) | UNIQUE, NOT NULL | Реферальный код |
| bonus_earned | DECIMAL(10,2) | DEFAULT 0 | Заработанный бонус |
| referred_user_active | BOOLEAN | DEFAULT FALSE | Активен ли приглашённый |
| referred_user_premium | BOOLEAN | DEFAULT FALSE | Купил ли премиум |
| referred_profile_created | BOOLEAN | DEFAULT FALSE | Создан ли профиль |
| referred_first_match | BOOLEAN | DEFAULT FALSE | Первый мэтч |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата приглашения |
| activated_at | TIMESTAMPTZ | | Дата активации |

**Индексы:**
- `idx_referrals_referrer` (referrer_id)
- `idx_referrals_code` (referral_code)

---

### 14. sessions

**Описание:** Сессии пользователей для управления кэшированием.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| user_id | UUID | FK → users(id), NOT NULL | Пользователь |
| session_token | VARCHAR(255) | UNIQUE, NOT NULL | Токен сессии |
| redis_cache_key | VARCHAR(255) | | Ключ кэша Redis |
| cached_profiles_count | SMALLINT | DEFAULT 0 | Количество в кэше |
| current_profile_index | SMALLINT | DEFAULT 0 | Текущий индекс |
| last_profile_shown_at | TIMESTAMPTZ | | Последняя показанная анкета |
| device_info | JSONB | | Информация об устройстве |
| ip_address | VARCHAR(45) | | IP-адрес |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли |
| expires_at | TIMESTAMPTZ | NOT NULL | Дата истечения |
| last_heartbeat_at | TIMESTAMPTZ | | Последний heartbeat |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_sessions_user` (user_id) WHERE is_active = true
- `idx_sessions_token` (session_token)
- `idx_sessions_expires` (expires_at) WHERE is_active = true

---

### 15. daily_limits

**Описание:** Rate limiting — дневные лимиты действий.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| profile_id | UUID | FK → profiles(id), NOT NULL | Профиль |
| date | DATE | NOT NULL, DEFAULT CURRENT_DATE | Дата |
| swipes_count | SMALLINT | DEFAULT 0 | Сделано свайпов |
| swipes_limit | SMALLINT | DEFAULT 50 | Лимит свайпов (free) |
| super_likes_count | SMALLINT | DEFAULT 0 | Сделано super likes |
| super_likes_limit | SMALLINT | DEFAULT 3 | Лимит super likes |
| messages_count | SMALLINT | DEFAULT 0 | Отправлено сообщений |
| messages_limit | SMALLINT | DEFAULT 200 | Лимит сообщений |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

---

### 16. notifications

**Описание:** Уведомления пользователей.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| user_id | UUID | FK → users(id), NOT NULL | Пользователь |
| type | VARCHAR(30) | NOT NULL | Тип: new_match, new_message, new_like, system |
| title | VARCHAR(200) | NOT NULL | Заголовок |
| body | TEXT | | Текст |
| data | JSONB | DEFAULT '{}'::jsonb | Payload |
| is_sent | BOOLEAN | DEFAULT FALSE | Отправлено |
| sent_at | TIMESTAMPTZ | | Дата отправки |
| is_read | BOOLEAN | DEFAULT FALSE | Прочитано |
| read_at | TIMESTAMPTZ | | Дата прочтения |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |

**Индексы:**
- `idx_notif_user_unread` (user_id, created_at DESC) WHERE is_read = false
- `idx_notif_unsent` (created_at) WHERE is_sent = false

---

### 17. metrics

**Описание:** Агрегированные метрики для аналитики.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| metric_name | VARCHAR(100) | NOT NULL | Название метрики |
| metric_type | metric_type_enum | NOT NULL | Тип: counter, gauge, histogram |
| metric_value | DECIMAL(20,6) | NOT NULL | Значение |
| dimensions | JSONB | DEFAULT '{}'::jsonb | Измерения |
| period_start | TIMESTAMPTZ | NOT NULL | Начало периода |
| period_end | TIMESTAMPTZ | NOT NULL | Конец периода |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |

**Индексы:**
- `idx_metrics_name_period` (metric_name, period_start DESC)

---

### 18. date_ideas

**Описание:** Идеи для свиданий.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| category | date_category_enum | NOT NULL | Категория |
| title | VARCHAR(200) | NOT NULL | Название |
| description | TEXT | | Описание |
| avg_cost | cost_level_enum | | Средняя стоимость |
| suitable_interests | JSONB | DEFAULT '[]'::jsonb | Подходящие интересы |
| city | VARCHAR(100) | | Город |
| country_code | CHAR(2) | | Страна |
| latitude | DECIMAL(9,6) | | Широта |
| longitude | DECIMAL(9,6) | | Долгота |
| suggested_count | INTEGER | DEFAULT 0 | Сколько раз предложено |
| positive_feedback_count | INTEGER | DEFAULT 0 | Положительных отзывов |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_date_ideas_city` (city, category) WHERE is_active = true
- `idx_date_ideas_interests` (suitable_interests) USING GIN

---

### 19. audit_log

**Описание:** Лог аудита действий пользователей.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY | Уникальный идентификатор |
| user_id | UUID | FK → users(id) | Пользователь |
| action | VARCHAR(50) | NOT NULL | Действие |
| entity_type | VARCHAR(50) | NOT NULL | Тип сущности |
| entity_id | UUID | NOT NULL | ID сущности |
| old_values | JSONB | | Старые значения |
| new_values | JSONB | | Новые значения |
| ip_address | VARCHAR(45) | | IP-адрес |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |

**Индексы:**
- `idx_audit_user` (user_id, created_at DESC)
- `idx_audit_entity` (entity_type, entity_id)

---

## Foreign Keys (сводная таблица)

| Таблица | Поле | Ссылается на |
|---------|------|--------------|
| profiles | user_id | users(id) |
| preferences | profile_id | profiles(id) |
| photos | profile_id | profiles(id) |
| photos | moderated_by | users(id) |
| swipes | swiper_id | profiles(id) |
| swipes | swiped_id | profiles(id) |
| matches | profile1_id | profiles(id) |
| matches | profile2_id | profiles(id) |
| matches | initiator_id | profiles(id) |
| matches | unmatched_by | profiles(id) |
| messages | match_id | matches(id) |
| messages | sender_id | profiles(id) |
| messages | reply_to_id | messages(id) |
| reports | reporter_profile_id | profiles(id) |
| reports | reported_profile_id | profiles(id) |
| reports | message_id | messages(id) |
| reports | reviewed_by | users(id) |
| blocks | blocker_profile_id | profiles(id) |
| blocks | blocked_profile_id | profiles(id) |
| ratings_primary | profile_id | profiles(id) |
| ratings_behavioral | profile_id | profiles(id) |
| ratings_combined | profile_id | profiles(id) |
| referrals | referrer_id | users(id) |
| referrals | referred_id | users(id) |
| sessions | user_id | users(id) |
| daily_limits | profile_id | profiles(id) |
| notifications | user_id | users(id) |
| audit_log | user_id | users(id) |

---

## Redis-структуры для кэширования

### Ключи Redis

| Ключ | Тип | Описание | TTL |
|------|-----|----------|-----|
| `ranked_profiles:{user_id}:{session_id}` | LIST | Кэш 10 отранжированных анкет на сессию | 3600 сек |
| `session:{telegram_id}` | HASH | Данные сессии пользователя | 3600 сек |
| `ratelimit:{telegram_id}:{action}` | COUNTER | Rate limiting для действий | 60 сек |
| `celery:*` | Various | Задачи Celery | Зависит от задачи |
| `swipe_lock:{swiper_id}:{swiped_id}` | STRING | Блокировка от дублирования свайпа | 30 сек |
| `match_notification:{match_id}` | STRING | Флаг уведомления о мэтче | 300 сек |
| `profile_viewed:{user_id}:{profile_id}` | STRING | Факт просмотра анкеты | 86400 сек |

---

## Формулы расчёта рейтингов

### Первичный рейтинг (ratings_primary)
```
total_score = completeness_score * 0.30 + photo_score * 0.30 + preference_match_score * 0.20 + verification_bonus * 0.20
```

### Поведенческий рейтинг (ratings_behavioral)
```
total_score = like_count_score * 0.25 + like_pass_ratio_score * 0.25 + match_rate_score * 0.20 + conversation_initiation_score * 0.15 + response_rate_score * 0.10 + activity_pattern_score * 0.05
```

### Комбинированный рейтинг (ratings_combined)
```
total_score = primary_score * 0.40 + behavioral_score * 0.50 + referral_bonus * 0.10
```

---

## Ключевые изменения в версии 2.0

| Изменение | Описание |
|-----------|----------|
| **ENUM типы** | 12 ENUM вместо VARCHAR + CHECK |
| **date_of_birth** | Вместо age — возраст вычисляется |
| **Безопасность** | Таблицы `reports`, `blocks` |
| **Soft delete** | `deleted_at` в users, photos, messages |
| **AI-модерация** | `nsfw_score`, `face_detected` в photos |
| **Rate limiting** | Таблица `daily_limits` |
| **Уведомления** | Таблица `notifications` |
| **Аудит** | Таблица `audit_log` |
| **Монетизация** | `super_like` в swipes, лимиты в daily_limits |
| **Улучшенные matches** | Переименовано user → profile, кэш сообщений |
