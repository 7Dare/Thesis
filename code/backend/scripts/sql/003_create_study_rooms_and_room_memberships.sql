CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS study_rooms (
    room_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_name VARCHAR(120) NOT NULL,
    host_user_id UUID NOT NULL REFERENCES users(user_id),
    duration_minutes INT NOT NULL CHECK (duration_minutes > 0),
    started_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL,
    closed_at TIMESTAMPTZ,
    invite_code VARCHAR(12) NOT NULL UNIQUE,
    max_members INT NOT NULL DEFAULT 6,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS room_memberships (
    membership_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES study_rooms(room_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    role VARCHAR(20) NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at TIMESTAMPTZ,
    leave_reason VARCHAR(40),
    is_muted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_room_memberships_room_user_joined UNIQUE (room_id, user_id, joined_at)
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_study_rooms_set_updated_at ON study_rooms;
CREATE TRIGGER trg_study_rooms_set_updated_at
BEFORE UPDATE ON study_rooms
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_study_rooms_status_ends_at
    ON study_rooms(status, ends_at);

CREATE INDEX IF NOT EXISTS idx_study_rooms_invite_code
    ON study_rooms(invite_code);

CREATE INDEX IF NOT EXISTS idx_room_memberships_room_left_at
    ON room_memberships(room_id, left_at);

CREATE INDEX IF NOT EXISTS idx_room_memberships_room_user_joined_desc
    ON room_memberships(room_id, user_id, joined_at DESC);
