# ConnectMe — Схема базы данных PostgreSQL

**Версия:** 1.0.0  
**Дата создания:** 2026-03-16  
**Проект:** ConnectMe Dating Bot

---

## Обзор

Схема базы данных разработана для микросервисной системы знакомств ConnectMe с поддержкой:
- Регистрации и управления профилями
- Системы свайпов и мэтчей
- Многоуровневой системы рейтингов (первичный, поведенческий, комбинированный)
- Icebreaker-вопросов для начала разговора
- Реферальной программы
- Сессионного управления
- Метрик и аналитики

---

## Таблицы

### 1. users

**Описание:** Базовая сущность пользователя Telegram. Содержит информацию из Telegram API.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор пользователя |
| telegram_id | BIGINT | UNIQUE, NOT NULL | ID пользователя в Telegram |
| username | VARCHAR(255) | | Имя пользователя в Telegram |
| first_name | VARCHAR(255) | NOT NULL | Имя |
| last_name | VARCHAR(255) | | Фамилия |
| language_code | VARCHAR(10) | DEFAULT 'ru' | Язык интерфейса |
| is_bot | BOOLEAN | DEFAULT FALSE | Является ли ботом |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата регистрации |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата последнего обновления |

**Индексы:**
- `idx_users_telegram_id` (telegram_id) — для быстрого поиска по Telegram ID
- `idx_users_created_at` (created_at) — для аналитики по регистрациям

---

### 2. profiles

**Описание:** Расширенный профиль пользователя для знакомств. Содержит информацию для подбора пар.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор профиля |
| user_id | UUID | FOREIGN KEY → users(id), UNIQUE, NOT NULL | Ссылка на пользователя |
| age | INTEGER | CHECK (age >= 18) | Возраст пользователя |
| gender | VARCHAR(20) | CHECK (gender IN ('male', 'female', 'other')), NOT NULL | Пол |
| bio | TEXT | | Описание профиля (биография) |
| interests | JSONB | DEFAULT '[]'::jsonb | Список интересов |
| city | VARCHAR(100) | | Город проживания |
| latitude | DECIMAL(9,6) | CHECK (latitude BETWEEN -90 AND 90) | Широта |
| longitude | DECIMAL(9,6) | CHECK (longitude BETWEEN -180 AND 180) | Долгота |
| looking_for | VARCHAR(20) | CHECK (looking_for IN ('male', 'female', 'both')), NOT NULL | Кого ищет |
| age_range_min | INTEGER | DEFAULT 18, CHECK (age_range_min >= 18) | Мин. возраст для поиска |
| age_range_max | INTEGER | DEFAULT 100, CHECK (age_range_max <= 100) | Макс. возраст для поиска |
| distance_max_km | INTEGER | DEFAULT 100, CHECK (distance_max_km >= 1) | Макс. расстояние в км |
| is_active | BOOLEAN | DEFAULT TRUE | Активен ли профиль |
| is_verified | BOOLEAN | DEFAULT FALSE | Верифицирован ли профиль |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания профиля |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата последнего обновления |

**Индексы:**
- `idx_profiles_user_id` (user_id) — для поиска профиля по пользователю
- `idx_profiles_gender_looking_for` (gender, looking_for, is_active) — для подбора анкет
- `idx_profiles_location` (city, latitude, longitude) — для гео-поиска
- `idx_profiles_age_range` (age, is_active) — для фильтрации по возрасту
- `idx_profiles_interests` (interests) USING GIN — для поиска по интересам (JSONB)

---

### 3. preferences

**Описание:** Детальные предпочтения пользователя для тонкой настройки подбора.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| profile_id | UUID | FOREIGN KEY → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| preferred_cities | JSONB | DEFAULT '[]'::jsonb | Предпочтительные города |
| education_preference | VARCHAR(50) | | Предпочтение по образованию |
| occupation_preference | VARCHAR(50) | | Предпочтение по роду занятий |
| relationship_goals | VARCHAR(50) | CHECK (relationship_goals IN ('casual', 'serious', 'friendship', 'networking')) | Цель знакомства |
| deal_breakers | JSONB | DEFAULT '[]'::jsonb | Недопустимые качества |
| importance_weights | JSONB | DEFAULT '{"age": 0.2, "distance": 0.3, "interests": 0.5}'::jsonb | Веса параметров подбора |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_preferences_profile_id` (profile_id) — для поиска предпочтений профиля

---

### 4. swipes

**Описание:** История действий пользователей (лайки/пропуски).

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор свайпа |
| swiper_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Кто сделал свайп |
| swiped_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Кого свайпнули |
| action | VARCHAR(10) | CHECK (action IN ('like', 'pass')), NOT NULL | Действие (like/pass) |
| context_data | JSONB | DEFAULT '{}'::jsonb | Контекст (рейтинги, интересы) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата свайпа |

**Индексы:**
- `idx_swipes_swiper_id` (swiper_id) — для истории свайпов пользователя
- `idx_swipes_swiped_id` (swiped_id) — для проверки кто лайкнул
- `idx_swipes_pair` (swiper_id, swiped_id, action) — для проверки взаимных лайков
- `idx_swipes_created_at` (created_at) — для аналитики по времени
- `idx_swipes_action` (action, created_at) — для статистики лайков/пропусков

**Уникальные ограничения:**
- `uniq_swipes_pair` UNIQUE (swiper_id, swiped_id) — один свайп на пару

---

### 5. matches

**Описание:** Взаимные лайки (мэтчи). Создаётся при взаимном like.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор мэтча |
| user1_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Первый пользователь |
| user2_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Второй пользователь |
| status | VARCHAR(20) | DEFAULT 'active', CHECK (status IN ('active', 'archived', 'blocked')) | Статус мэтча |
| initiator_id | UUID | FOREIGN KEY → profiles(id) | Кто начал общение первым |
| last_message_at | TIMESTAMPTZ | | Дата последнего сообщения |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания мэтча |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_matches_user1_id` (user1_id) — для поиска мэтчей пользователя
- `idx_matches_user2_id` (user2_id) — для поиска мэтчей пользователя
- `idx_matches_status` (status) — для фильтрации активных мэтчей
- `idx_matches_users_combined` (user1_id, user2_id, status) — для быстрого поиска
- `idx_matches_last_message` (last_message_at DESC) — для сортировки по активности

**Уникальные ограничения:**
- `uniq_matches_pair` UNIQUE (user1_id, user2_id) — один мэтч на пару

---

### 6. messages

**Описание:** Сообщения в чате между мэтчами.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор сообщения |
| match_id | UUID | FOREIGN KEY → matches(id), NOT NULL | Ссылка на мэтч |
| sender_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Отправитель |
| content | TEXT | NOT NULL | Текст сообщения |
| message_type | VARCHAR(20) | DEFAULT 'text', CHECK (message_type IN ('text', 'photo', 'icebreaker', 'voice')) | Тип сообщения |
| media_urls | JSONB | DEFAULT '[]'::jsonb | Ссылки на медиа (для photo) |
| is_read | BOOLEAN | DEFAULT FALSE | Прочитано ли |
| read_at | TIMESTAMPTZ | | Дата прочтения |
| reply_to_id | UUID | FOREIGN KEY → messages(id) | Ответ на сообщение |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата отправки |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_messages_match_id` (match_id) — для сообщений мэтча
- `idx_messages_match_created` (match_id, created_at) — для хронологии чата
- `idx_messages_sender_id` (sender_id) — для сообщений пользователя
- `idx_messages_is_read` (is_read, created_at) — для непрочитанных
- `idx_messages_type` (message_type, created_at) — для статистики по типам

---

### 7. icebreaker_questions

**Описание:** База вопросов для функции «Ледокол».

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор вопроса |
| category | VARCHAR(30) | CHECK (category IN ('general', 'hobbies', 'travel', 'food', 'entertainment', 'deep', 'philosophical', 'funny')), NOT NULL | Категория вопроса |
| question_text | TEXT | NOT NULL | Текст вопроса |
| difficulty | VARCHAR(10) | DEFAULT 'light', CHECK (difficulty IN ('light', 'medium', 'deep')) | Уровень сложности |
| tags | JSONB | DEFAULT '[]'::jsonb | Теги для подбора по интересам |
| usage_count | INTEGER | DEFAULT 0, CHECK (usage_count >= 0) | Количество использований |
| success_rate | DECIMAL(5,4) | DEFAULT 0.5, CHECK (success_rate BETWEEN 0 AND 1) | Процент успешных диалогов |
| avg_response_time_sec | INTEGER | | Среднее время ответа (сек) |
| is_active | BOOLEAN | DEFAULT TRUE | Активен ли вопрос |
| created_by | UUID | FOREIGN KEY → users(id) | Кто создал вопрос |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_icebreaker_category` (category, is_active) — для поиска по категории
- `idx_icebreaker_difficulty` (difficulty, is_active) — для поиска по сложности
- `idx_icebreaker_tags` (tags) USING GIN — для поиска по тегам (JSONB)
- `idx_icebreaker_success_rate` (success_rate DESC, is_active) — для топа успешных
- `idx_icebreaker_usage` (usage_count ASC, is_active) — для малоиспользованных

---

### 8. icebreaker_usage

**Описание:** История использования icebreaker-вопросов для аналитики.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор записи |
| question_id | UUID | FOREIGN KEY → icebreaker_questions(id), NOT NULL | Использованный вопрос |
| sender_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Кто отправил вопрос |
| recipient_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Кому отправлен вопрос |
| match_id | UUID | FOREIGN KEY → matches(id), NOT NULL | Мэтч, в котором использован |
| message_id | UUID | FOREIGN KEY → messages(id) | Сообщение с вопросом |
| was_responded | BOOLEAN | DEFAULT FALSE | Был ли получен ответ |
| response_time_sec | INTEGER | | Время ответа в секундах |
| conversation_started | BOOLEAN | DEFAULT FALSE | Начался ли диалог после вопроса |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата использования |

**Индексы:**
- `idx_icebreaker_usage_question` (question_id) — для статистики вопроса
- `idx_icebreaker_usage_sender` (sender_id) — для истории пользователя
- `idx_icebreaker_usage_match` (match_id) — для истории мэтча
- `idx_icebreaker_usage_responded` (was_responded, created_at) — для аналитики ответов
- `idx_icebreaker_usage_created` (created_at) — для временной аналитики

---

### 9. ratings_primary

**Описание:** Первичный рейтинг на основе данных анкеты.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| profile_id | UUID | FOREIGN KEY → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| completeness_score | DECIMAL(5,4) | DEFAULT 0, CHECK (completeness_score BETWEEN 0 AND 1) | Полнота анкеты (30%) |
| photo_score | DECIMAL(5,4) | DEFAULT 0, CHECK (photo_score BETWEEN 0 AND 1) | Качество фото (30%) |
| preference_match_score | DECIMAL(5,4) | DEFAULT 0, CHECK (preference_match_score BETWEEN 0 AND 1) | Соответствие предпочтениям (20%) |
| verification_bonus | DECIMAL(5,4) | DEFAULT 0, CHECK (verification_bonus BETWEEN 0 AND 1) | Бонус за верификацию (20%) |
| total_score | DECIMAL(5,4) | GENERATED ALWAYS AS (completeness_score * 0.3 + photo_score * 0.3 + preference_match_score * 0.2 + verification_bonus * 0.2) STORED | Итоговый первичный рейтинг |
| calculated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата расчёта |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания записи |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_ratings_primary_profile` (profile_id) — для поиска рейтинга профиля
- `idx_ratings_primary_total` (total_score DESC) — для топа пользователей
- `idx_ratings_primary_calculated` (calculated_at) — для отслеживания актуальности

---

### 10. ratings_behavioral

**Описание:** Поведенческий рейтинг на основе активности пользователя.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| profile_id | UUID | FOREIGN KEY → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| like_count_score | DECIMAL(5,4) | DEFAULT 0, CHECK (like_count_score BETWEEN 0 AND 1) | Количество полученных лайков (25%) |
| like_pass_ratio_score | DECIMAL(5,4) | DEFAULT 0, CHECK (like_pass_ratio_score BETWEEN 0 AND 1) | Соотношение лайков/пропусков (25%) |
| match_rate_score | DECIMAL(5,4) | DEFAULT 0, CHECK (match_rate_score BETWEEN 0 AND 1) | Частота мэтчей (20%) |
| conversation_initiation_score | DECIMAL(5,4) | DEFAULT 0, CHECK (conversation_initiation_score BETWEEN 0 AND 1) | Инициирование диалогов (15%) |
| activity_pattern_score | DECIMAL(5,4) | DEFAULT 0, CHECK (activity_pattern_score BETWEEN 0 AND 1) | Паттерны активности (15%) |
| total_score | DECIMAL(5,4) | GENERATED ALWAYS AS (like_count_score * 0.25 + like_pass_ratio_score * 0.25 + match_rate_score * 0.2 + conversation_initiation_score * 0.15 + activity_pattern_score * 0.15) STORED | Итоговый поведенческий рейтинг |
| period_start | DATE | NOT NULL | Начало периода расчёта |
| period_end | DATE | NOT NULL | Конец периода расчёта |
| calculated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата расчёта |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания записи |

**Индексы:**
- `idx_ratings_behavioral_profile` (profile_id) — для поиска рейтинга профиля
- `idx_ratings_behavioral_total` (total_score DESC) — для топа пользователей
- `idx_ratings_behavioral_period` (period_start, period_end) — для периодов
- `idx_ratings_behavioral_calculated` (calculated_at) — для отслеживания актуальности

---

### 11. ratings_combined

**Описание:** Комбинированный рейтинг — интеграция первичного и поведенческого с реферальным бонусом.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| profile_id | UUID | FOREIGN KEY → profiles(id), UNIQUE, NOT NULL | Ссылка на профиль |
| primary_score | DECIMAL(5,4) | NOT NULL, CHECK (primary_score BETWEEN 0 AND 1) | Первичный рейтинг (40%) |
| behavioral_score | DECIMAL(5,4) | NOT NULL, CHECK (behavioral_score BETWEEN 0 AND 1) | Поведенческий рейтинг (40%) |
| referral_bonus | DECIMAL(5,4) | DEFAULT 0, CHECK (referral_bonus BETWEEN 0 AND 1) | Реферальный бонус (20%) |
| total_score | DECIMAL(5,4) | GENERATED ALWAYS AS (primary_score * 0.4 + behavioral_score * 0.4 + referral_bonus * 0.2) STORED | Итоговый комбинированный рейтинг |
| rank_position | INTEGER | | Позиция в глобальном рейтинге |
| percentile | DECIMAL(5,4) | | Процентиль пользователя |
| calculated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата расчёта |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания записи |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_ratings_combined_profile` (profile_id) — для поиска рейтинга профиля
- `idx_ratings_combined_total` (total_score DESC) — для глобального топа
- `idx_ratings_combined_rank` (rank_position) — для позиции в рейтинге
- `idx_ratings_combined_percentile` (percentile DESC) — для процентилей
- `idx_ratings_combined_calculated` (calculated_at) — для отслеживания актуальности

---

### 12. referrals

**Описание:** Реферальная программа — приглашения друзей.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| referrer_id | UUID | FOREIGN KEY → users(id), NOT NULL | Кто пригласил |
| referred_id | UUID | FOREIGN KEY → users(id), UNIQUE, NOT NULL | Кого пригласили |
| referral_code | VARCHAR(50) | UNIQUE | Реферальный код |
| bonus_earned | DECIMAL(10,2) | DEFAULT 0 | Заработанный бонус |
| referred_user_active | BOOLEAN | DEFAULT FALSE | Активен ли приглашённый |
| referred_user_premium | BOOLEAN | DEFAULT FALSE | Купил ли премиум приглашённый |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата приглашения |
| activated_at | TIMESTAMPTZ | | Дата активации приглашённым |

**Индексы:**
- `idx_referrals_referrer` (referrer_id) — для рефералов пользователя
- `idx_referrals_referred` (referred_id) — для кто пригласил
- `idx_referrals_code` (referral_code) — для поиска по коду
- `idx_referrals_active` (referred_user_active, created_at) — для активных рефералов

---

### 13. sessions

**Описание:** Сессии пользователей для управления кэшированием анкет.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор сессии |
| user_id | UUID | FOREIGN KEY → users(id), NOT NULL | Пользователь |
| session_token | VARCHAR(255) | UNIQUE, NOT NULL | Токен сессии |
| redis_cache_key | VARCHAR(255) | | Ключ кэша в Redis |
| cached_profiles_count | INTEGER | DEFAULT 0 | Количество закэшированных анкет |
| current_profile_index | INTEGER | DEFAULT 0 | Текущий индекс в кэше |
| last_profile_shown_at | TIMESTAMPTZ | | Когда показана последняя анкета |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли сессия |
| expires_at | TIMESTAMPTZ | NOT NULL | Дата истечения сессии |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Дата обновления |

**Индексы:**
- `idx_sessions_user_id` (user_id) — для сессий пользователя
- `idx_sessions_token` (session_token) — для поиска по токену
- `idx_sessions_expires` (expires_at) — для очистки истёкших
- `idx_sessions_active` (is_active, expires_at) — для активных сессий

---

### 14. metrics

**Описание:** Агрегированные метрики для аналитики.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| metric_name | VARCHAR(100) | NOT NULL | Название метрики |
| metric_type | VARCHAR(20) | CHECK (metric_type IN ('counter', 'gauge', 'histogram')), NOT NULL | Тип метрики |
| metric_value | DECIMAL(20,6) | NOT NULL | Значение метрики |
| dimensions | JSONB | DEFAULT '{}'::jsonb | Измерения (user_id, service, etc.) |
| period_start | TIMESTAMPTZ | NOT NULL | Начало периода |
| period_end | TIMESTAMPTZ | NOT NULL | Конец периода |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания записи |

**Индексы:**
- `idx_metrics_name` (metric_name) — для поиска по метрике
- `idx_metrics_period` (period_start, period_end) — для периодов
- `idx_metrics_name_period` (metric_name, period_start) — комбинированный индекс
- `idx_metrics_dimensions` (dimensions) USING GIN — для поиска по измерениям (JSONB)

---

## Дополнительные таблицы (опционально)

### photos

**Описание:** Метаданные фотографий профилей.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| profile_id | UUID | FOREIGN KEY → profiles(id), NOT NULL | Ссылка на профиль |
| s3_key | VARCHAR(500) | NOT NULL | Ключ в S3/Minio |
| s3_bucket | VARCHAR(100) | DEFAULT 'profile-photos' | Бакет S3 |
| is_primary | BOOLEAN | DEFAULT FALSE | Основное фото |
| order | INTEGER | DEFAULT 0 | Порядок отображения |
| file_size_bytes | BIGINT | | Размер файла |
| mime_type | VARCHAR(50) | DEFAULT 'image/jpeg' | Тип файла |
| width | INTEGER | | Ширина в пикселях |
| height | INTEGER | | Высота в пикселях |
| is_moderated | BOOLEAN | DEFAULT FALSE | Прошло ли модерацию |
| moderation_status | VARCHAR(20) | DEFAULT 'pending' | Статус модерации |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата загрузки |

**Индексы:**
- `idx_photos_profile_id` (profile_id) — для фото профиля
- `idx_photos_primary` (profile_id, is_primary) — для основного фото
- `idx_photos_order` (profile_id, order) — для сортировки фото

---

### date_ideas

**Описание:** Идеи для свиданий.

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Уникальный идентификатор |
| category | VARCHAR(30) | CHECK (category IN ('cafe', 'activity', 'outdoor', 'cultural', 'entertainment')), NOT NULL | Категория |
| title | VARCHAR(200) | NOT NULL | Название |
| description | TEXT | | Описание |
| avg_cost | VARCHAR(20) | CHECK (avg_cost IN ('free', 'low', 'medium', 'high')) | Средняя стоимость |
| suitable_interests | JSONB | DEFAULT '[]'::jsonb | Подходящие интересы |
| city | VARCHAR(100) | | Город |
| latitude | DECIMAL(9,6) | | Широта |
| longitude | DECIMAL(9,6) | | Долгота |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли идея |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Дата создания |

**Индексы:**
- `idx_date_ideas_category` (category, is_active) — для поиска по категории
- `idx_date_ideas_city` (city, is_active) — для поиска по городу
- `idx_date_ideas_interests` (suitable_interests) USING GIN — для поиска по интересам

---

## Foreign Keys (сводная таблица)

| Таблица | Поле | Ссылается на |
|---------|------|--------------|
| profiles | user_id | users(id) |
| preferences | profile_id | profiles(id) |
| swipes | swiper_id | profiles(id) |
| swipes | swiped_id | profiles(id) |
| matches | user1_id | profiles(id) |
| matches | user2_id | profiles(id) |
| matches | initiator_id | profiles(id) |
| messages | match_id | matches(id) |
| messages | sender_id | profiles(id) |
| messages | reply_to_id | messages(id) |
| icebreaker_questions | created_by | users(id) |
| icebreaker_usage | question_id | icebreaker_questions(id) |
| icebreaker_usage | sender_id | profiles(id) |
| icebreaker_usage | recipient_id | profiles(id) |
| icebreaker_usage | match_id | matches(id) |
| icebreaker_usage | message_id | messages(id) |
| ratings_primary | profile_id | profiles(id) |
| ratings_behavioral | profile_id | profiles(id) |
| ratings_combined | profile_id | profiles(id) |
| referrals | referrer_id | users(id) |
| referrals | referred_id | users(id) |
| sessions | user_id | users(id) |
| photos | profile_id | profiles(id) |

---

## Индексы для оптимизации (сводная таблица)

### Основные индексы производительности

```sql
-- Пользователи
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Профили
CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_profiles_gender_looking_for ON profiles(gender, looking_for, is_active);
CREATE INDEX idx_profiles_location ON profiles(city, latitude, longitude);
CREATE INDEX idx_profiles_age_range ON profiles(age, is_active);
CREATE INDEX idx_profiles_interests ON profiles USING GIN (interests);

-- Предпочтения
CREATE INDEX idx_preferences_profile_id ON preferences(profile_id);

-- Свайпы
CREATE INDEX idx_swipes_swiper_id ON swipes(swiper_id);
CREATE INDEX idx_swipes_swiped_id ON swipes(swiped_id);
CREATE INDEX idx_swipes_pair ON swipes(swiper_id, swiped_id, action);
CREATE INDEX idx_swipes_created_at ON swipes(created_at);
CREATE INDEX idx_swipes_action ON swipes(action, created_at);
CREATE UNIQUE INDEX uniq_swipes_pair ON swipes(swiper_id, swiped_id);

-- Мэтчи
CREATE INDEX idx_matches_user1_id ON matches(user1_id);
CREATE INDEX idx_matches_user2_id ON matches(user2_id);
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_users_combined ON matches(user1_id, user2_id, status);
CREATE INDEX idx_matches_last_message ON matches(last_message_at DESC);
CREATE UNIQUE INDEX uniq_matches_pair ON matches(user1_id, user2_id);

-- Сообщения
CREATE INDEX idx_messages_match_id ON messages(match_id);
CREATE INDEX idx_messages_match_created ON messages(match_id, created_at);
CREATE INDEX idx_messages_sender_id ON messages(sender_id);
CREATE INDEX idx_messages_is_read ON messages(is_read, created_at);
CREATE INDEX idx_messages_type ON messages(message_type, created_at);

-- Icebreaker вопросы
CREATE INDEX idx_icebreaker_category ON icebreaker_questions(category, is_active);
CREATE INDEX idx_icebreaker_difficulty ON icebreaker_questions(difficulty, is_active);
CREATE INDEX idx_icebreaker_tags ON icebreaker_questions USING GIN (tags);
CREATE INDEX idx_icebreaker_success_rate ON icebreaker_questions(success_rate DESC, is_active);
CREATE INDEX idx_icebreaker_usage_count ON icebreaker_questions(usage_count ASC, is_active);

-- Icebreaker использования
CREATE INDEX idx_icebreaker_usage_question ON icebreaker_usage(question_id);
CREATE INDEX idx_icebreaker_usage_sender ON icebreaker_usage(sender_id);
CREATE INDEX idx_icebreaker_usage_match ON icebreaker_usage(match_id);
CREATE INDEX idx_icebreaker_usage_responded ON icebreaker_usage(was_responded, created_at);
CREATE INDEX idx_icebreaker_usage_created ON icebreaker_usage(created_at);

-- Рейтинги (первичный)
CREATE INDEX idx_ratings_primary_profile ON ratings_primary(profile_id);
CREATE INDEX idx_ratings_primary_total ON ratings_primary(total_score DESC);
CREATE INDEX idx_ratings_primary_calculated ON ratings_primary(calculated_at);

-- Рейтинги (поведенческий)
CREATE INDEX idx_ratings_behavioral_profile ON ratings_behavioral(profile_id);
CREATE INDEX idx_ratings_behavioral_total ON ratings_behavioral(total_score DESC);
CREATE INDEX idx_ratings_behavioral_period ON ratings_behavioral(period_start, period_end);
CREATE INDEX idx_ratings_behavioral_calculated ON ratings_behavioral(calculated_at);

-- Рейтинги (комбинированный)
CREATE INDEX idx_ratings_combined_profile ON ratings_combined(profile_id);
CREATE INDEX idx_ratings_combined_total ON ratings_combined(total_score DESC);
CREATE INDEX idx_ratings_combined_rank ON ratings_combined(rank_position);
CREATE INDEX idx_ratings_combined_percentile ON ratings_combined(percentile DESC);
CREATE INDEX idx_ratings_combined_calculated ON ratings_combined(calculated_at);

-- Рефералы
CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX idx_referrals_referred ON referrals(referred_id);
CREATE INDEX idx_referrals_code ON referrals(referral_code);
CREATE INDEX idx_referrals_active ON referrals(referred_user_active, created_at);

-- Сессии
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
CREATE INDEX idx_sessions_active ON sessions(is_active, expires_at);

-- Метрики
CREATE INDEX idx_metrics_name ON metrics(metric_name);
CREATE INDEX idx_metrics_period ON metrics(period_start, period_end);
CREATE INDEX idx_metrics_name_period ON metrics(metric_name, period_start);
CREATE INDEX idx_metrics_dimensions ON metrics USING GIN (dimensions);

-- Фото (опционально)
CREATE INDEX idx_photos_profile_id ON photos(profile_id);
CREATE INDEX idx_photos_primary ON photos(profile_id, is_primary);
CREATE INDEX idx_photos_order ON photos(profile_id, order);

-- Идеи для свиданий (опционально)
CREATE INDEX idx_date_ideas_category ON date_ideas(category, is_active);
CREATE INDEX idx_date_ideas_city ON date_ideas(city, is_active);
CREATE INDEX idx_date_ideas_interests ON date_ideas USING GIN (suitable_interests);
```

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

### Структура кэша анкет

```
ranked_profiles:{user_id}:{session_id} = [
  {
    "profile_id": "uuid",
    "user_id": "uuid",
    "age": 25,
    "gender": "female",
    "city": "Moscow",
    "interests": ["travel", "music"],
    "bio": "...",
    "photo_urls": ["url1", "url2"],
    "combined_score": 0.85,
    "distance_km": 5.2,
    "match_probability": 0.72
  },
  ...
] (10 анкет)
```

---

## Триггеры (опционально)

### Автоматическое обновление updated_at

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применить ко всем таблицам с updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ... и так далее для всех таблиц с updated_at
```

---

## Примечания

1. **UUID используется как основной тип ID** для распределённой системы и безопасности
2. **TIMESTAMPTZ** (с часовым поясом) для корректной работы с разными часовыми поясами
3. **JSONB** для гибких полей (интересы, предпочтения, метрики) с поддержкой индексации GIN
4. **CHECK constraints** для валидации данных на уровне БД
5. **GENERATED ALWAYS AS** для вычисляемых полей рейтингов
6. **PostGIS** может быть добавлен для сложных гео-запросов (расстояние между координатами)

---

*Схема разработана для проекта ConnectMe — автономной системы разработки Telegram-ботов*
