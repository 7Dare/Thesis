DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'username'
    ) THEN
        ALTER TABLE users RENAME COLUMN username TO login_user_id;
    END IF;
END $$;

ALTER TABLE users
    ALTER COLUMN login_user_id TYPE VARCHAR(64),
    ALTER COLUMN login_user_id SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_username_key'
    ) THEN
        ALTER TABLE users RENAME CONSTRAINT users_username_key TO users_login_user_id_key;
    ELSIF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_login_user_id_key'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_login_user_id_key UNIQUE (login_user_id);
    END IF;
END $$;
