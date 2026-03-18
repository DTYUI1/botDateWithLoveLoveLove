

# Ревью и улучшение схемы ConnectMe Dating Bot

Привет! Я внимательно проанализировал твою схему. В целом она хорошо продумана, но есть ряд важных улучшений. Разберу по категориям.

## Улучшенная схема

```dbml
// ConnectMe Database Schema - DBML for dbdiagram.io
// Проект: ConnectMe Dating Bot
// Версия: 2.0.0
// Дата: 2026-03-16

// ============================================================================
// ENUMS (вместо строковых CHECK — типобезопасность и единый источник правды)
// ============================================================================

Enum gender_enum {
  male
  female
  other
}

Enum looking_for_enum {
  male
  female
  both
}

Enum relationship_goal_enum {
  casual
  serious
  friendship
  networking
}

Enum swipe_action_enum {
  like
  pass
  super_like    // добавлено: монетизация / приоритет
}

Enum match_status_enum {
  active
  archived
  blocked
  unmatched     // добавлено: важно отличать от archived
}

Enum moderation_status_enum {
  pending
  approved
  rejected
  under_review  // добавлено: для ручной модерации
}

Enum metric_type_enum {
  counter
  gauge
  histogram
}

Enum date_category_enum {
  cafe
  activity
  outdoor
  cultural
  entertainment
}

Enum cost_level_enum {
  free
  low
  medium
  high
}

Enum report_reason_enum {
  spam
  fake_profile
  harassment
  inappropriate_content
  underage
  other
}

Enum report_status_enum {
  open
  investigating
  resolved
  dismissed
}

Enum block_reason_enum {
  manual
  report
  system
}

// ============================================================================
// USERS & AUTHENTICATION
// ============================================================================

Table users {
  id uuid [pk, default: `gen_random_uuid()`]
  telegram_id bigint [unique, not null]
  username varchar(255)
  first_name varchar(255) [not null]
  last_name varchar(255)
  language_code varchar(10) [default: 'ru']
  is_bot boolean [default: false]
  is_banned boolean [default: false]          // добавлено: глобальный бан
  ban_reason text                              // добавлено
  banned_at timestamptz                        // добавлено
  last_active_at timestamptz                   // добавлено: для определения "мёртвых" аккаунтов
  deleted_at timestamptz                       // добавлено: soft delete
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_users_telegram_id ON users(telegram_id);
    - CREATE INDEX idx_users_last_active ON users(last_active_at) WHERE deleted_at IS NULL;
    
    Триггер:
    - updated_at = now() ON UPDATE
  '''
}

Table profiles {
  id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [unique, not null, ref: > users.id]
  
  // --- Основная информация ---
  display_name varchar(100)                    // добавлено: имя для показа (может отличаться от telegram)
  date_of_birth date                           // ИЗМЕНЕНО: вместо age — возраст вычисляется
  gender gender_enum [not null]                // ИЗМЕНЕНО: enum вместо varchar + CHECK
  bio text [note: 'макс. ~1000 символов, ограничение на уровне приложения']
  height_cm smallint                           // добавлено: популярный фильтр
  
  // --- Интересы ---
  interests jsonb [default: `'[]'::jsonb`]
  
  // --- Геолокация ---
  city varchar(100)
  country_code char(2)                         // добавлено: ISO 3166-1 alpha-2
  latitude decimal(9,6) [check: `latitude BETWEEN -90 AND 90`]
  longitude decimal(9,6) [check: `longitude BETWEEN -180 AND 180`]
  location_updated_at timestamptz              // добавлено: важно для актуальности геоданных
  
  // --- Предпочтения поиска (перенесены из preferences для упрощения запросов) ---
  looking_for looking_for_enum [not null]      // ИЗМЕНЕНО: enum
  age_range_min smallint [default: 18, check: `age_range_min >= 18`]
  age_range_max smallint [default: 100, check: `age_range_max <= 100`]
  distance_max_km smallint [default: 100, check: `distance_max_km BETWEEN 1 AND 500`]
  
  // --- Статусы ---
  is_active boolean [default: true]
  is_verified boolean [default: false]
  verified_at timestamptz                      // добавлено
  profile_completion_pct smallint [default: 0] // добавлено: кэш, 0-100
  
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    КРИТИЧЕСКИЕ CONSTRAINTS:
    - CHECK (age_range_min <= age_range_max)
    - CHECK (date_of_birth <= CURRENT_DATE - INTERVAL '18 years')
    - CHECK (height_cm BETWEEN 100 AND 250 OR height_cm IS NULL)
    
    Индексы:
    - CREATE INDEX idx_profiles_active_gender ON profiles(gender, is_active) WHERE is_active = true;
    - CREATE INDEX idx_profiles_city ON profiles(city) WHERE is_active = true;
    - CREATE INDEX idx_profiles_location ON profiles USING GIST (
        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
      ) WHERE is_active = true AND latitude IS NOT NULL;
      -- Требует PostGIS!
    - CREATE INDEX idx_profiles_dob ON profiles(date_of_birth) WHERE is_active = true;
    - GIN index on interests для поиска по пересечению
  '''
}

Table preferences {
  id uuid [pk, default: `gen_random_uuid()`]
  profile_id uuid [unique, not null, ref: > profiles.id]
  
  preferred_cities jsonb [default: `'[]'::jsonb`]
  preferred_countries jsonb [default: `'[]'::jsonb`]    // добавлено
  education_preference varchar(50)
  occupation_preference varchar(50)
  relationship_goals relationship_goal_enum             // ИЗМЕНЕНО: enum
  height_min_cm smallint                                // добавлено
  height_max_cm smallint                                // добавлено
  deal_breakers jsonb [default: `'[]'::jsonb`]
  importance_weights jsonb [default: `'{"age": 0.2, "distance": 0.3, "interests": 0.5}'::jsonb`]
  
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    CHECK (height_min_cm <= height_max_cm OR height_min_cm IS NULL OR height_max_cm IS NULL)
    
    Валидация importance_weights на уровне приложения:
    - все значения >= 0 и <= 1
    - сумма = 1.0
  '''
}

Table photos {
  id uuid [pk, default: `gen_random_uuid()`]
  profile_id uuid [not null, ref: > profiles.id]
  
  // --- Хранение ---
  s3_key varchar(500) [not null]
  s3_bucket varchar(100) [default: 'profile-photos']
  thumbnail_s3_key varchar(500)                // добавлено: превью для быстрой загрузки
  blurhash varchar(50)                         // добавлено: placeholder при загрузке
  
  // --- Метаданные ---
  is_primary boolean [default: false]
  sort_order smallint [default: 0]             // ПЕРЕИМЕНОВАНО: "order" — зарезервированное слово
  file_size_bytes integer                      // ИЗМЕНЕНО: integer достаточно (до 2GB)
  mime_type varchar(50) [default: 'image/jpeg']
  width smallint                               // ИЗМЕНЕНО: smallint достаточно для пикселей
  height smallint
  
  // --- Модерация ---
  moderation_status moderation_status_enum [default: 'pending']  // ИЗМЕНЕНО: enum
  moderated_by uuid [ref: > users.id]          // добавлено: кто модерировал
  moderated_at timestamptz                     // добавлено
  rejection_reason text                        // добавлено: обратная связь
  
  // --- AI модерация ---
  nsfw_score decimal(3,2)                      // добавлено: от ML-модели, 0.00-1.00
  face_detected boolean                        // добавлено: проверка наличия лица
  
  deleted_at timestamptz                       // добавлено: soft delete
  created_at timestamptz [default: `now()`]

  Note: '''
    CONSTRAINTS:
    - Максимум 1 is_primary = true на profile_id:
      CREATE UNIQUE INDEX idx_photos_primary 
        ON photos(profile_id) WHERE is_primary = true AND deleted_at IS NULL;
    - CHECK (sort_order >= 0 AND sort_order < 10)
    
    Индексы:
    - CREATE INDEX idx_photos_profile ON photos(profile_id, sort_order) WHERE deleted_at IS NULL;
  '''
}

// ============================================================================
// SWIPES & MATCHES
// ============================================================================

Table swipes {
  id uuid [pk, default: `gen_random_uuid()`]
  swiper_id uuid [not null, ref: > profiles.id]
  swiped_id uuid [not null, ref: > profiles.id]
  action swipe_action_enum [not null]          // ИЗМЕНЕНО: enum + super_like
  
  // --- Контекст для аналитики ---
  source varchar(20)                           // добавлено: 'discovery', 'daily_picks', 'nearby'
  time_spent_ms integer                        // добавлено: сколько смотрел профиль (для ML)
  context_data jsonb [default: `'{}'::jsonb`]
  
  created_at timestamptz [default: `now()`]

  Note: '''
    КРИТИЧЕСКИЕ CONSTRAINTS:
    - UNIQUE(swiper_id, swiped_id) — нельзя свайпнуть дважды
    - CHECK(swiper_id != swiped_id) — нельзя свайпнуть себя
    
    Индексы:
    - CREATE UNIQUE INDEX idx_swipes_pair ON swipes(swiper_id, swiped_id);
    - CREATE INDEX idx_swipes_swiped ON swipes(swiped_id, action) WHERE action = 'like';
      -- Для быстрого определения мэтча (есть ли встречный лайк?)
    - CREATE INDEX idx_swipes_created ON swipes(created_at);
      -- Для ограничения свайпов в день
    
    Партиционирование:
    - По created_at (RANGE, monthly) — таблица растёт быстрее всех
  '''
}

Table matches {
  id uuid [pk, default: `gen_random_uuid()`]
  profile1_id uuid [not null, ref: > profiles.id]   // ПЕРЕИМЕНОВАНО: profile вместо user
  profile2_id uuid [not null, ref: > profiles.id]
  status match_status_enum [default: 'active']       // ИЗМЕНЕНО: enum
  initiator_id uuid [ref: > profiles.id]
  
  // --- Статистика переписки (кэш) ---
  message_count integer [default: 0]                  // добавлено
  last_message_at timestamptz
  last_message_preview varchar(100)                   // добавлено: для списка чатов
  
  // --- Мета ---
  unmatched_by uuid [ref: > profiles.id]              // добавлено: кто размэтчил
  unmatched_at timestamptz                            // добавлено
  
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    КРИТИЧЕСКИЕ CONSTRAINTS:
    - CHECK(profile1_id < profile2_id) — каноническая пара, исключает дубли
    - UNIQUE(profile1_id, profile2_id)
    
    Индексы:
    - CREATE UNIQUE INDEX idx_matches_pair ON matches(profile1_id, profile2_id);
    - CREATE INDEX idx_matches_profile1 ON matches(profile1_id, status) WHERE status = 'active';
    - CREATE INDEX idx_matches_profile2 ON matches(profile2_id, status) WHERE status = 'active';
    - CREATE INDEX idx_matches_last_msg ON matches(last_message_at DESC) WHERE status = 'active';
  '''
}

Table messages {
  id uuid [pk, default: `gen_random_uuid()`]
  match_id uuid [not null, ref: > matches.id]
  sender_id uuid [not null, ref: > profiles.id]
  
  // --- Контент ---
  content text                                 // ИЗМЕНЕНО: nullable (для сообщений с медиа без текста)
  message_type varchar(20) [default: 'text']   // добавлено: 'text', 'image', 'voice', 'gif', 'sticker'
  media_urls jsonb [default: `'[]'::jsonb`]
  
  // --- Статус доставки ---
  is_read boolean [default: false]
  read_at timestamptz
  is_delivered boolean [default: false]        // добавлено
  delivered_at timestamptz                     // добавлено
  
  // --- Ответы и редактирование ---
  reply_to_id uuid [ref: > messages.id]
  is_edited boolean [default: false]           // добавлено
  edited_at timestamptz                        // добавлено
  deleted_at timestamptz                       // добавлено: soft delete
  
  created_at timestamptz [default: `now()`]

  Note: '''
    CONSTRAINTS:
    - CHECK(content IS NOT NULL OR media_urls != '[]'::jsonb)
      -- Хотя бы текст или медиа
    
    Индексы:
    - CREATE INDEX idx_messages_match ON messages(match_id, created_at DESC) WHERE deleted_at IS NULL;
    - CREATE INDEX idx_messages_unread ON messages(match_id, sender_id) 
        WHERE is_read = false AND deleted_at IS NULL;
    
    Партиционирование:
    - По created_at (RANGE, monthly) — основной объём данных
  '''
}

// ============================================================================
// SAFETY: REPORTS & BLOCKS
// ============================================================================

Table reports {
  id uuid [pk, default: `gen_random_uuid()`]
  reporter_profile_id uuid [not null, ref: > profiles.id]
  reported_profile_id uuid [not null, ref: > profiles.id]
  reason report_reason_enum [not null]
  description text
  evidence_urls jsonb [default: `'[]'::jsonb`]     // скриншоты и т.д.
  message_id uuid [ref: > messages.id]              // конкретное сообщение, если применимо
  status report_status_enum [default: 'open']
  reviewed_by uuid [ref: > users.id]                // модератор
  reviewed_at timestamptz
  resolution_notes text
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_reports_status ON reports(status) WHERE status IN ('open', 'investigating');
    - CREATE INDEX idx_reports_reported ON reports(reported_profile_id);
    - UNIQUE(reporter_profile_id, reported_profile_id, reason) — нельзя пожаловаться дважды по тому же поводу
  '''
}

Table blocks {
  id uuid [pk, default: `gen_random_uuid()`]
  blocker_profile_id uuid [not null, ref: > profiles.id]
  blocked_profile_id uuid [not null, ref: > profiles.id]
  reason block_reason_enum [default: 'manual']
  created_at timestamptz [default: `now()`]

  Note: '''
    CONSTRAINTS:
    - UNIQUE(blocker_profile_id, blocked_profile_id)
    - CHECK(blocker_profile_id != blocked_profile_id)
    
    Индексы:
    - CREATE INDEX idx_blocks_blocker ON blocks(blocker_profile_id);
    - CREATE INDEX idx_blocks_blocked ON blocks(blocked_profile_id);
    
    Используется при формировании выдачи: 
    WHERE swiped_id NOT IN (SELECT blocked_profile_id FROM blocks WHERE blocker_profile_id = ?)
    AND swiper_id NOT IN (SELECT blocked_profile_id FROM blocks WHERE blocker_profile_id = ?)
  '''
}

// ============================================================================
// RATING SYSTEM (3 LEVELS) — оптимизированный
// ============================================================================

Table ratings_primary {
  id uuid [pk, default: `gen_random_uuid()`]
  profile_id uuid [unique, not null, ref: > profiles.id]
  
  completeness_score decimal(5,4) [default: 0, check: `completeness_score BETWEEN 0 AND 1`]
  photo_score decimal(5,4) [default: 0, check: `photo_score BETWEEN 0 AND 1`]
  photo_count smallint [default: 0]            // добавлено: для быстрой проверки без JOIN
  preference_match_score decimal(5,4) [default: 0, check: `preference_match_score BETWEEN 0 AND 1`]
  verification_bonus decimal(5,4) [default: 0, check: `verification_bonus BETWEEN 0 AND 1`]
  total_score decimal(5,4) [default: 0, check: `total_score BETWEEN 0 AND 1`]
  
  version integer [default: 1]                 // добавлено: оптимистичная блокировка
  calculated_at timestamptz [default: `now()`]
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_ratings_primary_score ON ratings_primary(total_score DESC);
  '''
}

Table ratings_behavioral {
  id uuid [pk, default: `gen_random_uuid()`]
  profile_id uuid [not null, ref: > profiles.id]  // НЕ unique — исторические записи за разные периоды
  
  like_received_count integer [default: 0]     // добавлено: абсолютное значение для отладки
  pass_received_count integer [default: 0]     // добавлено
  
  like_count_score decimal(5,4) [default: 0, check: `like_count_score BETWEEN 0 AND 1`]
  like_pass_ratio_score decimal(5,4) [default: 0, check: `like_pass_ratio_score BETWEEN 0 AND 1`]
  match_rate_score decimal(5,4) [default: 0, check: `match_rate_score BETWEEN 0 AND 1`]
  conversation_initiation_score decimal(5,4) [default: 0, check: `conversation_initiation_score BETWEEN 0 AND 1`]
  response_rate_score decimal(5,4) [default: 0, check: `response_rate_score BETWEEN 0 AND 1`]  // добавлено
  activity_pattern_score decimal(5,4) [default: 0, check: `activity_pattern_score BETWEEN 0 AND 1`]
  total_score decimal(5,4) [default: 0, check: `total_score BETWEEN 0 AND 1`]
  
  period_start date [not null]
  period_end date [not null]
  calculated_at timestamptz [default: `now()`]
  created_at timestamptz [default: `now()`]

  Note: '''
    CONSTRAINTS:
    - CHECK(period_start < period_end)
    - UNIQUE(profile_id, period_start, period_end)
    
    Индексы:
    - CREATE INDEX idx_ratings_beh_profile_period 
        ON ratings_behavioral(profile_id, period_end DESC);
    
    Партиционирование по period_end (monthly) для автоочистки старых периодов
  '''
}

Table ratings_combined {
  id uuid [pk, default: `gen_random_uuid()`]
  profile_id uuid [unique, not null, ref: > profiles.id]
  
  primary_score decimal(5,4) [not null, check: `primary_score BETWEEN 0 AND 1`]
  primary_weight decimal(3,2) [default: 0.40]  // добавлено: настраиваемый вес
  behavioral_score decimal(5,4) [not null, check: `behavioral_score BETWEEN 0 AND 1`]
  behavioral_weight decimal(3,2) [default: 0.50]
  referral_bonus decimal(5,4) [default: 0, check: `referral_bonus BETWEEN 0 AND 1`]
  referral_weight decimal(3,2) [default: 0.10]
  
  total_score decimal(5,4) [default: 0, check: `total_score BETWEEN 0 AND 1`]
  rank_position integer
  percentile decimal(5,4)
  tier varchar(10) [note: 'S/A/B/C/D — для быстрой сегментации в выдаче']  // добавлено
  
  calculated_at timestamptz [default: `now()`]
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_ratings_combined_score ON ratings_combined(total_score DESC);
    - CREATE INDEX idx_ratings_combined_tier ON ratings_combined(tier);
    
    Используется в основном запросе выдачи кандидатов
  '''
}

// ============================================================================
// REFERRALS & SESSIONS
// ============================================================================

Table referrals {
  id uuid [pk, default: `gen_random_uuid()`]
  referrer_id uuid [not null, ref: > users.id]
  referred_id uuid [unique, not null, ref: > users.id]
  referral_code varchar(50) [unique, not null]  // ИЗМЕНЕНО: not null
  
  // --- Статус ---
  bonus_earned decimal(10,2) [default: 0]
  referred_user_active boolean [default: false]
  referred_user_premium boolean [default: false]
  
  // --- Вехи ---
  referred_profile_created boolean [default: false]   // добавлено
  referred_first_match boolean [default: false]        // добавлено
  
  created_at timestamptz [default: `now()`]
  activated_at timestamptz

  Note: '''
    CONSTRAINTS:
    - CHECK(referrer_id != referred_id) — нельзя пригласить себя
    
    Индексы:
    - CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);
    - CREATE INDEX idx_referrals_code ON referrals(referral_code);
  '''
}

Table sessions {
  id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null, ref: > users.id]
  session_token varchar(255) [unique, not null]
  
  // --- Кэш профилей ---
  redis_cache_key varchar(255)
  cached_profiles_count smallint [default: 0]   // ИЗМЕНЕНО: smallint достаточно
  current_profile_index smallint [default: 0]
  last_profile_shown_at timestamptz
  
  // --- Устройство (для безопасности) ---
  device_info jsonb                              // добавлено
  ip_address inet                                // добавлено: тип inet для IP
  
  // --- Жизненный цикл ---
  is_active boolean [default: true]
  expires_at timestamptz [not null]
  last_heartbeat_at timestamptz                  // добавлено: для обнаружения зависших сессий
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_sessions_user ON sessions(user_id) WHERE is_active = true;
    - CREATE INDEX idx_sessions_token ON sessions(session_token);
    - CREATE INDEX idx_sessions_expires ON sessions(expires_at) WHERE is_active = true;
    
    Cron-задача: деактивировать сессии WHERE expires_at < now()
  '''
}

// ============================================================================
// RATE LIMITING & ANTI-ABUSE
// ============================================================================

Table daily_limits {
  id uuid [pk, default: `gen_random_uuid()`]
  profile_id uuid [not null, ref: > profiles.id]
  date date [not null, default: `CURRENT_DATE`]
  
  swipes_count smallint [default: 0]
  swipes_limit smallint [default: 50]          // free tier: 50/day
  super_likes_count smallint [default: 0]
  super_likes_limit smallint [default: 3]
  messages_count smallint [default: 0]
  messages_limit smallint [default: 200]
  
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    - UNIQUE(profile_id, date)
    - Партиционирование по date (daily или weekly) + автоочистка через 30 дней
  '''
}

// ============================================================================
// NOTIFICATIONS
// ============================================================================

Table notifications {
  id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null, ref: > users.id]
  type varchar(30) [not null]                  // 'new_match', 'new_message', 'new_like', 'system'
  title varchar(200) [not null]
  body text
  data jsonb [default: `'{}'::jsonb`]          // payload: match_id, message_id, etc.
  is_sent boolean [default: false]
  sent_at timestamptz
  is_read boolean [default: false]
  read_at timestamptz
  created_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_notif_user_unread ON notifications(user_id, created_at DESC) 
        WHERE is_read = false;
    - CREATE INDEX idx_notif_unsent ON notifications(created_at) WHERE is_sent = false;
    
    TTL: удалять через 90 дней
  '''
}

// ============================================================================
// ANALYTICS & METRICS
// ============================================================================

Table metrics {
  id uuid [pk, default: `gen_random_uuid()`]
  metric_name varchar(100) [not null]
  metric_type metric_type_enum [not null]       // ИЗМЕНЕНО: enum
  metric_value decimal(20,6) [not null]
  dimensions jsonb [default: `'{}'::jsonb`]
  period_start timestamptz [not null]
  period_end timestamptz [not null]
  created_at timestamptz [default: `now()`]

  Note: '''
    CONSTRAINTS:
    - CHECK(period_start < period_end)
    
    Индексы:
    - CREATE INDEX idx_metrics_name_period ON metrics(metric_name, period_start DESC);
    
    Партиционирование по period_start (monthly)
  '''
}

// ============================================================================
// CONTENT: DATE IDEAS
// ============================================================================

Table date_ideas {
  id uuid [pk, default: `gen_random_uuid()`]
  category date_category_enum [not null]        // ИЗМЕНЕНО: enum
  title varchar(200) [not null]
  description text
  avg_cost cost_level_enum                      // ИЗМЕНЕНО: enum
  suitable_interests jsonb [default: `'[]'::jsonb`]
  city varchar(100)
  country_code char(2)                          // добавлено
  latitude decimal(9,6)
  longitude decimal(9,6)
  
  // --- Мета ---
  suggested_count integer [default: 0]          // добавлено: сколько раз предложено
  positive_feedback_count integer [default: 0]  // добавлено
  
  is_active boolean [default: true]
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]

  Note: '''
    Индексы:
    - CREATE INDEX idx_date_ideas_city ON date_ideas(city, category) WHERE is_active = true;
    - GIN index on suitable_interests
  '''
}

// ============================================================================
// AUDIT LOG (для compliance и отладки)
// ============================================================================

Table audit_log {
  id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [ref: > users.id]
  action varchar(50) [not null]                // 'profile_update', 'photo_delete', 'account_delete', ...
  entity_type varchar(50) [not null]           // 'profile', 'photo', 'match', ...
  entity_id uuid [not null]
  old_values jsonb
  new_values jsonb
  ip_address inet
  created_at timestamptz [default: `now()`]

  Note: '''
    - Append-only, никогда не UPDATE/DELETE
    - Партиционирование по created_at (monthly)
    - TTL: 1 год (или по требованиям GDPR)
    
    Индексы:
    - CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);
    - CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
  '''
}
```

---

## 📋 Сводка изменений

### Структурные
| Что | Было | Стало | Почему |
|-----|------|-------|--------|
| `age` в profiles | integer | `date_of_birth date` | Возраст устаревает, дата рождения — нет |
| `gender`, `action` и др. | varchar + CHECK | **Enum** | Типобезопасность, производительность |
| `"order"` в photos | Зарезервированное слово | `sort_order` | Избежание ошибок SQL |
| `user1_id/user2_id` | Без ограничений | `CHECK(profile1_id < profile2_id)` + UNIQUE | Исключение дублей мэтчей |
| swipes | Без UNIQUE | `UNIQUE(swiper_id, swiped_id)` | Нельзя лайкнуть дважды |
| `integer` для размеров | integer | **smallint** где уместно | Экономия ~50% на этих столбцах |

### Новые таблицы
| Таблица | Назначение |
|---------|-----------|
| `reports` | Жалобы на пользователей — **обязательно** для dating-приложения |
| `blocks` | Блокировка пользователей — исключение из выдачи |
| `daily_limits` | Rate limiting свайпов/сообщений — анти-спам + монетизация |
| `notifications` | Очередь уведомлений — new match, messages, system |
| `audit_log` | Аудит действий — безопасность, GDPR, отладка |

### Новые поля в существующих таблицах
| Таблица | Новые поля | Зачем |
|---------|-----------|-------|
| users | `is_banned`, `last_active_at`, `deleted_at` | Модерация, soft delete |
| profiles | `display_name`, `height_cm`, `country_code`, `location_updated_at` | Больше фильтров, актуальность |
| photos | `thumbnail_s3_key`, `blurhash`, `nsfw_score`, `face_detected` | UX + AI модерация |
| swipes | `source`, `time_spent_ms` | ML-аналитика |
| matches | `message_count`, `last_message_preview`, `unmatched_by` | Кэш для списка чатов |
| messages | `message_type`, `is_delivered`, `is_edited` | Полноценный чат |
| sessions | `device_info`, `ip_address`, `last_heartbeat_at` | Безопасность |

### Производительность
- **PostGIS** для геопоиска вместо формулы Haversine в каждом запросе
- **Партиционирование** swipes, messages, metrics, audit_log по дате
- **Partial indexes** (`WHERE is_active = true`, `WHERE deleted_at IS NULL`)
- **GIN indexes** для jsonb-полей (interests, suitable_interests)
- **Кэш-поля** (`message_count`, `profile_completion_pct`) для избежания тяжёлых агрегаций

Эта схема готова к продакшену с нагрузкой порядка сотен тысяч пользователей. Для масштабирования до миллионов потребуется дополнительно рассмотреть шардирование и вынос чатов в отдельный сервис.