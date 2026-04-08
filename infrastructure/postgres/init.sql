-- ConnectMe Database Schema
-- Инициализационный скрипт для PostgreSQL

-- ============================================
-- ENUMS
-- ============================================

CREATE TYPE gender_enum AS ENUM ('male', 'female', 'other');
CREATE TYPE looking_for_enum AS ENUM ('male', 'female', 'both');
CREATE TYPE relationship_goal_enum AS ENUM ('casual', 'serious', 'friendship', 'networking');
CREATE TYPE swipe_action_enum AS ENUM ('like', 'pass', 'super_like');
CREATE TYPE match_status_enum AS ENUM ('active', 'archived', 'blocked', 'unmatched');
CREATE TYPE moderation_status_enum AS ENUM ('pending', 'approved', 'rejected', 'under_review');
CREATE TYPE report_reason_enum AS ENUM ('spam', 'fake_profile', 'harassment', 'inappropriate_content', 'underage', 'other');
CREATE TYPE report_status_enum AS ENUM ('open', 'investigating', 'resolved', 'dismissed');
CREATE TYPE block_reason_enum AS ENUM ('manual', 'report', 'system');
CREATE TYPE date_category_enum AS ENUM ('cafe', 'activity', 'outdoor', 'cultural', 'entertainment');
CREATE TYPE cost_level_enum AS ENUM ('free', 'low', 'medium', 'high');

-- ============================================
-- USERS
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255),
    language_code VARCHAR(10) DEFAULT 'ru',
    is_banned BOOLEAN DEFAULT FALSE,
    ban_reason TEXT,
    banned_at TIMESTAMPTZ,
    last_active_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_last_active ON users(last_active_at) WHERE last_active_at IS NOT NULL;

-- ============================================
-- PROFILES
-- ============================================

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id),
    display_name VARCHAR(100),
    date_of_birth DATE NOT NULL,
    gender gender_enum NOT NULL,
    bio TEXT,
    height_cm SMALLINT,
    interests JSONB DEFAULT '[]'::jsonb,
    city VARCHAR(100),
    country_code CHAR(2),
    latitude DECIMAL(9,6) CHECK (latitude BETWEEN -90 AND 90),
    longitude DECIMAL(9,6) CHECK (longitude BETWEEN -180 AND 180),
    location_updated_at TIMESTAMPTZ,
    looking_for looking_for_enum NOT NULL,
    age_range_min SMALLINT DEFAULT 18 CHECK (age_range_min >= 18),
    age_range_max SMALLINT DEFAULT 100 CHECK (age_range_max <= 100),
    distance_max_km SMALLINT DEFAULT 100 CHECK (distance_max_km BETWEEN 1 AND 500),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    profile_completion_pct SMALLINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_profiles_active_gender ON profiles(is_active, gender) WHERE is_active = TRUE;
CREATE INDEX idx_profiles_city ON profiles(city) WHERE city IS NOT NULL;
CREATE INDEX idx_profiles_location ON profiles(latitude, longitude) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
CREATE INDEX idx_profiles_dob ON profiles(date_of_birth);
CREATE INDEX idx_profiles_interests ON profiles USING GIN(interests);

-- ============================================
-- PHOTOS
-- ============================================

CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    s3_key VARCHAR(500) NOT NULL,
    s3_bucket VARCHAR(100) DEFAULT 'profile-photos',
    thumbnail_s3_key VARCHAR(500),
    blurhash VARCHAR(50),
    is_primary BOOLEAN DEFAULT FALSE,
    sort_order SMALLINT DEFAULT 0,
    file_size_bytes INTEGER,
    mime_type VARCHAR(50) DEFAULT 'image/jpeg',
    width SMALLINT,
    height SMALLINT,
    moderation_status moderation_status_enum DEFAULT 'pending',
    moderated_by UUID REFERENCES users(id),
    moderated_at TIMESTAMPTZ,
    rejection_reason TEXT,
    nsfw_score DECIMAL(3,2),
    face_detected BOOLEAN,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_photos_profile ON photos(profile_id);
CREATE INDEX idx_photos_primary ON photos(profile_id, is_primary) WHERE is_primary = TRUE;

-- ============================================
-- SWIPES
-- ============================================

CREATE TABLE IF NOT EXISTS swipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    swiper_id UUID NOT NULL REFERENCES profiles(id),
    swiped_id UUID NOT NULL REFERENCES profiles(id),
    action swipe_action_enum NOT NULL,
    source VARCHAR(20),
    time_spent_ms INTEGER,
    context_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_swipes_pair ON swipes(swiper_id, swiped_id);
CREATE INDEX idx_swipes_swiped ON swipes(swiped_id);
CREATE INDEX idx_swipes_created ON swipes(created_at);

-- ============================================
-- MATCHES
-- ============================================

CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile1_id UUID NOT NULL REFERENCES profiles(id),
    profile2_id UUID NOT NULL REFERENCES profiles(id),
    status match_status_enum DEFAULT 'active',
    initiator_id UUID REFERENCES profiles(id),
    message_count INTEGER DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    last_message_preview VARCHAR(100),
    unmatched_by UUID REFERENCES profiles(id),
    unmatched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_matches_pair ON matches(profile1_id, profile2_id);
CREATE INDEX idx_matches_profile1 ON matches(profile1_id) WHERE status = 'active';
CREATE INDEX idx_matches_profile2 ON matches(profile2_id) WHERE status = 'active';
CREATE INDEX idx_matches_last_msg ON matches(last_message_at) WHERE last_message_at IS NOT NULL;

-- ============================================
-- MESSAGES
-- ============================================

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES matches(id),
    sender_id UUID NOT NULL REFERENCES profiles(id),
    content TEXT,
    message_type VARCHAR(20) DEFAULT 'text',
    media_urls JSONB DEFAULT '[]'::jsonb,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    is_delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMPTZ,
    reply_to_id UUID REFERENCES messages(id),
    is_edited BOOLEAN DEFAULT FALSE,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_match ON messages(match_id);
CREATE INDEX idx_messages_unread ON messages(match_id, is_read) WHERE is_read = FALSE;

-- ============================================
-- RATINGS PRIMARY
-- ============================================

CREATE TABLE IF NOT EXISTS ratings_primary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID UNIQUE NOT NULL REFERENCES profiles(id),
    completeness_score DECIMAL(5,4) DEFAULT 0 CHECK (completeness_score BETWEEN 0 AND 1),
    photo_score DECIMAL(5,4) DEFAULT 0 CHECK (photo_score BETWEEN 0 AND 1),
    photo_count SMALLINT DEFAULT 0,
    preference_match_score DECIMAL(5,4) DEFAULT 0 CHECK (preference_match_score BETWEEN 0 AND 1),
    verification_bonus DECIMAL(5,4) DEFAULT 0 CHECK (verification_bonus BETWEEN 0 AND 1),
    total_score DECIMAL(5,4) DEFAULT 0 CHECK (total_score BETWEEN 0 AND 1),
    version INTEGER DEFAULT 1,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ratings_primary_profile ON ratings_primary(profile_id);
CREATE INDEX idx_ratings_primary_score ON ratings_primary(total_score DESC);

-- ============================================
-- RATINGS BEHAVIORAL
-- ============================================

CREATE TABLE IF NOT EXISTS ratings_behavioral (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    like_received_count INTEGER DEFAULT 0,
    pass_received_count INTEGER DEFAULT 0,
    like_count_score DECIMAL(5,4) DEFAULT 0 CHECK (like_count_score BETWEEN 0 AND 1),
    like_pass_ratio_score DECIMAL(5,4) DEFAULT 0 CHECK (like_pass_ratio_score BETWEEN 0 AND 1),
    match_rate_score DECIMAL(5,4) DEFAULT 0 CHECK (match_rate_score BETWEEN 0 AND 1),
    conversation_initiation_score DECIMAL(5,4) DEFAULT 0 CHECK (conversation_initiation_score BETWEEN 0 AND 1),
    response_rate_score DECIMAL(5,4) DEFAULT 0 CHECK (response_rate_score BETWEEN 0 AND 1),
    activity_pattern_score DECIMAL(5,4) DEFAULT 0 CHECK (activity_pattern_score BETWEEN 0 AND 1),
    total_score DECIMAL(5,4) DEFAULT 0 CHECK (total_score BETWEEN 0 AND 1),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ratings_beh_profile_period ON ratings_behavioral(profile_id, period_start, period_end);

-- ============================================
-- RATINGS COMBINED
-- ============================================

CREATE TABLE IF NOT EXISTS ratings_combined (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID UNIQUE NOT NULL REFERENCES profiles(id),
    primary_score DECIMAL(5,4) NOT NULL CHECK (primary_score BETWEEN 0 AND 1),
    primary_weight DECIMAL(3,2) DEFAULT 0.40,
    behavioral_score DECIMAL(5,4) NOT NULL CHECK (behavioral_score BETWEEN 0 AND 1),
    behavioral_weight DECIMAL(3,2) DEFAULT 0.50,
    referral_bonus DECIMAL(5,4) DEFAULT 0 CHECK (referral_bonus BETWEEN 0 AND 1),
    referral_weight DECIMAL(3,2) DEFAULT 0.10,
    total_score DECIMAL(5,4) DEFAULT 0 CHECK (total_score BETWEEN 0 AND 1),
    rank_position INTEGER,
    percentile DECIMAL(5,4),
    tier VARCHAR(10),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ratings_combined_profile ON ratings_combined(profile_id);
CREATE INDEX idx_ratings_combined_score ON ratings_combined(total_score DESC);
CREATE INDEX idx_ratings_combined_tier ON ratings_combined(tier);

-- ============================================
-- SESSIONS
-- ============================================

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    redis_cache_key VARCHAR(255),
    cached_profiles_count SMALLINT DEFAULT 0,
    current_profile_index SMALLINT DEFAULT 0,
    last_profile_shown_at TIMESTAMPTZ,
    device_info JSONB,
    ip_address VARCHAR(45),
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ NOT NULL,
    last_heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at) WHERE is_active = TRUE;

-- ============================================
-- DAILY LIMITS
-- ============================================

CREATE TABLE IF NOT EXISTS daily_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    swipes_count SMALLINT DEFAULT 0,
    swipes_limit SMALLINT DEFAULT 50,
    super_likes_count SMALLINT DEFAULT 0,
    super_likes_limit SMALLINT DEFAULT 3,
    messages_count SMALLINT DEFAULT 0,
    messages_limit SMALLINT DEFAULT 200,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_daily_limits_profile_date ON daily_limits(profile_id, date);

-- ============================================
-- Функция обновления updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_matches_updated_at BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Готово!
-- ============================================

COMMENT ON DATABASE connectme_db IS 'ConnectMe Dating Bot Database';
