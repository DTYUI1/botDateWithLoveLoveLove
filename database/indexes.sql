-- ConnectMe database indexes
-- Task 4.2: DB optimization for the current backend query patterns.
--
-- Apply after infrastructure/postgres/init.sql:
--   psql "$DATABASE_URL" -f database/indexes.sql
--
-- Notes:
-- - IF NOT EXISTS keeps the script idempotent.
-- - These indexes complement the base indexes from init.sql instead of reusing
--   their names, so the file can be applied to existing installations.

-- ============================================================================
-- Profiles / Matching
-- ============================================================================

-- MatchingService filters active profiles by city, gender and birth date, then
-- returns profile rows by id. This partial composite index keeps inactive
-- profiles out of the search path.
CREATE INDEX IF NOT EXISTS idx_profiles_matching_city_gender_dob
    ON profiles (city, gender, date_of_birth, id)
    WHERE is_active = TRUE;

-- Fallback matching path only needs a fast scan of active profile ids when the
-- user has no city/gender filters.
CREATE INDEX IF NOT EXISTS idx_profiles_active_id
    ON profiles (id)
    WHERE is_active = TRUE;

-- Profile lookup by user_id is already covered by a unique constraint, but this
-- partial index helps joins ignore soft-deleted users when that field is used.
CREATE INDEX IF NOT EXISTS idx_users_active_telegram
    ON users (telegram_id)
    WHERE deleted_at IS NULL;

-- ============================================================================
-- Photos
-- ============================================================================

-- PhotoService counts/lists only non-deleted photos and orders by sort_order.
CREATE INDEX IF NOT EXISTS idx_photos_active_profile_sort
    ON photos (profile_id, sort_order, created_at)
    WHERE deleted_at IS NULL;

-- Primary photo lookup should not scan deleted photos.
CREATE INDEX IF NOT EXISTS idx_photos_active_primary
    ON photos (profile_id)
    WHERE is_primary = TRUE AND deleted_at IS NULL;

-- Moderation queue support: newest pending/under_review photos first.
CREATE INDEX IF NOT EXISTS idx_photos_moderation_queue
    ON photos (moderation_status, created_at)
    WHERE deleted_at IS NULL
      AND moderation_status IN ('pending', 'under_review');

-- ============================================================================
-- Swipes
-- ============================================================================

-- Mutual-like detection and duplicate-pair checks.
CREATE INDEX IF NOT EXISTS idx_swipes_like_pair
    ON swipes (swiper_id, swiped_id, created_at)
    WHERE action IN ('like', 'super_like');

-- Celery behavioral rating counts received likes/passes by swiped profile.
CREATE INDEX IF NOT EXISTS idx_swipes_received_action
    ON swipes (swiped_id, action, created_at);

-- Daily/activity analytics by acting profile.
CREATE INDEX IF NOT EXISTS idx_swipes_swiper_action_created
    ON swipes (swiper_id, action, created_at DESC);

-- Long append-only swipe history benefits from BRIN for broad time windows.
CREATE INDEX IF NOT EXISTS idx_swipes_created_brin
    ON swipes USING BRIN (created_at);

-- ============================================================================
-- Matches
-- ============================================================================

-- Match lists filter active matches for either profile side and sort by newest
-- update/message activity.
CREATE INDEX IF NOT EXISTS idx_matches_active_profile1_updated
    ON matches (profile1_id, updated_at DESC)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_matches_active_profile2_updated
    ON matches (profile2_id, updated_at DESC)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_matches_active_last_message
    ON matches (last_message_at DESC)
    WHERE status = 'active'
      AND last_message_at IS NOT NULL;

-- ============================================================================
-- Messages
-- ============================================================================

-- Messages API reads one match history in chronological order and counts the
-- same filtered set.
CREATE INDEX IF NOT EXISTS idx_messages_match_created_active
    ON messages (match_id, created_at, id)
    WHERE deleted_at IS NULL;

-- Unread counters/notifications should not inspect deleted messages.
CREATE INDEX IF NOT EXISTS idx_messages_unread_active
    ON messages (match_id, sender_id, created_at)
    WHERE is_read = FALSE
      AND deleted_at IS NULL;

-- Behavioral rating counts sent non-deleted messages by sender.
CREATE INDEX IF NOT EXISTS idx_messages_sender_active
    ON messages (sender_id, created_at DESC)
    WHERE deleted_at IS NULL;

-- Long append-only message history benefits from BRIN for broad time windows.
CREATE INDEX IF NOT EXISTS idx_messages_created_brin
    ON messages USING BRIN (created_at);

-- ============================================================================
-- Ratings
-- ============================================================================

-- Matching ranks by combined score and then joins back to profile_id.
CREATE INDEX IF NOT EXISTS idx_ratings_combined_score_profile
    ON ratings_combined (total_score DESC NULLS LAST, profile_id);

-- Daily recalculation often touches stale ratings first.
CREATE INDEX IF NOT EXISTS idx_ratings_combined_calculated
    ON ratings_combined (calculated_at, profile_id);

CREATE INDEX IF NOT EXISTS idx_ratings_behavioral_period_end
    ON ratings_behavioral (period_end DESC, profile_id);

-- ============================================================================
-- Sessions / Limits
-- ============================================================================

-- Active session lookup and cleanup.
CREATE INDEX IF NOT EXISTS idx_sessions_active_user_expires
    ON sessions (user_id, expires_at)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_sessions_expired_active
    ON sessions (expires_at)
    WHERE is_active = TRUE;

-- Limit checks always address one profile for the current day.
CREATE INDEX IF NOT EXISTS idx_daily_limits_profile_date_desc
    ON daily_limits (profile_id, date DESC);

-- ============================================================================
-- Date Ideas
-- ============================================================================

-- DateIdeaService lists active ideas for a city/category and orders by feedback.
CREATE INDEX IF NOT EXISTS idx_date_ideas_city_category_rank
    ON date_ideas (
        city,
        category,
        positive_feedback_count DESC,
        suggested_count ASC,
        created_at DESC
    )
    WHERE is_active = TRUE;

-- Same ranking when city is not specified.
CREATE INDEX IF NOT EXISTS idx_date_ideas_category_rank
    ON date_ideas (
        category,
        positive_feedback_count DESC,
        suggested_count ASC,
        created_at DESC
    )
    WHERE is_active = TRUE;

-- Suggestions include global ideas with city IS NULL.
CREATE INDEX IF NOT EXISTS idx_date_ideas_global_rank
    ON date_ideas (
        category,
        positive_feedback_count DESC,
        suggested_count ASC,
        created_at DESC
    )
    WHERE is_active = TRUE
      AND city IS NULL;
