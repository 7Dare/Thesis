CREATE TABLE IF NOT EXISTS user_study_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(user_id),
    avg_session_minutes NUMERIC(8,2) NOT NULL DEFAULT 0,
    preferred_duration_minutes NUMERIC(8,2) NOT NULL DEFAULT 0,
    preferred_period VARCHAR(20),
    study_days_30d INT NOT NULL DEFAULT 0,
    total_minutes_30d INT NOT NULL DEFAULT 0,
    intensity_level VARCHAR(20) NOT NULL DEFAULT 'normal',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_room_tags (
    room_id UUID NOT NULL REFERENCES study_rooms(room_id),
    tag_code VARCHAR(40) NOT NULL,
    tag_name VARCHAR(40) NOT NULL,
    score NUMERIC(5,2) NOT NULL DEFAULT 1.0,
    source VARCHAR(20) NOT NULL DEFAULT 'rule',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (room_id, tag_code)
);

CREATE TABLE IF NOT EXISTS room_recommendation_logs (
    log_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id),
    room_id UUID NOT NULL REFERENCES study_rooms(room_id),
    match_score NUMERIC(6,4) NOT NULL,
    reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_study_profiles_intensity
    ON user_study_profiles(intensity_level, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_study_room_tags_tag_code
    ON study_room_tags(tag_code, score DESC);

CREATE INDEX IF NOT EXISTS idx_room_recommendation_logs_user_created
    ON room_recommendation_logs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_room_recommendation_logs_room_created
    ON room_recommendation_logs(room_id, created_at DESC);
