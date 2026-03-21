CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(20) NOT NULL DEFAULT 'room' CHECK (type = 'room'),
    room_id UUID NOT NULL UNIQUE REFERENCES study_rooms(room_id),
    created_by UUID NOT NULL REFERENCES users(user_id),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    message_id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    sender_user_id UUID REFERENCES users(user_id),
    content_type VARCHAR(20) NOT NULL DEFAULT 'text',
    content TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reply_to_message_id BIGINT REFERENCES messages(message_id),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    edited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_messages_content_type
        CHECK (content_type IN ('text', 'system')),
    CONSTRAINT chk_messages_sender_for_content_type
        CHECK (
            (content_type = 'text' AND sender_user_id IS NOT NULL)
            OR content_type = 'system'
        )
);

CREATE TABLE IF NOT EXISTS conversation_read_cursors (
    cursor_id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    last_read_message_id BIGINT REFERENCES messages(message_id),
    last_read_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_crc_conversation_user UNIQUE (conversation_id, user_id)
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversations_set_updated_at ON conversations;
CREATE TRIGGER trg_conversations_set_updated_at
BEFORE UPDATE ON conversations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_conversation_read_cursors_set_updated_at ON conversation_read_cursors;
CREATE TRIGGER trg_conversation_read_cursors_set_updated_at
BEFORE UPDATE ON conversation_read_cursors
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_conversations_type_room
    ON conversations(type, room_id);

CREATE INDEX IF NOT EXISTS idx_messages_conv_created_desc
    ON messages(conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_conv_msgid_desc
    ON messages(conversation_id, message_id DESC);

CREATE INDEX IF NOT EXISTS idx_messages_sender_created_desc
    ON messages(sender_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_crc_user_updated_desc
    ON conversation_read_cursors(user_id, updated_at DESC);
