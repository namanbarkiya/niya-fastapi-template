-- =============================================================================
-- NIYA SAAS TEMPLATE - PostgreSQL Setup Script
-- =============================================================================
-- Run this script against any PostgreSQL instance (local or cloud) to bootstrap
-- the full schema. Works with Postgres 14+.
--
-- Usage:
--   Local:  psql -U postgres -d your_db -f scripts/setup.sql
--   Cloud:  psql "postgresql://user:pass@host/db?sslmode=require" -f scripts/setup.sql
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid(), crypt()
CREATE EXTENSION IF NOT EXISTS "citext";      -- case-insensitive text for emails

-- =============================================================================
-- USERS  (core identity table)
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           CITEXT      UNIQUE NOT NULL,
    email_verified  BOOLEAN     NOT NULL DEFAULT FALSE,
    password_hash   TEXT,                        -- NULL for OAuth-only accounts
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- =============================================================================
-- USER PROFILES  (extended user data, compatible with social logins)
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_profiles (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID        UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Basic info
    full_name               VARCHAR(255),
    display_name            VARCHAR(50),
    first_name              VARCHAR(100),
    last_name               VARCHAR(100),

    -- Contact
    phone                   VARCHAR(50),
    country                 VARCHAR(100),
    timezone                VARCHAR(100)  NOT NULL DEFAULT 'UTC',
    locale                  VARCHAR(10)   NOT NULL DEFAULT 'en',

    -- Media
    avatar_url              TEXT,
    banner_url              TEXT,
    bio                     TEXT          CHECK (char_length(bio) <= 500),

    -- Social links
    website                 TEXT,
    twitter_url             TEXT,
    linkedin_url            TEXT,
    github_url              TEXT,

    -- Professional
    company                 VARCHAR(100),
    job_title               VARCHAR(100),
    industry                VARCHAR(50),

    -- Preferences
    is_public               BOOLEAN       NOT NULL DEFAULT FALSE,
    email_notifications     BOOLEAN       NOT NULL DEFAULT TRUE,
    push_notifications      BOOLEAN       NOT NULL DEFAULT TRUE,
    marketing_emails        BOOLEAN       NOT NULL DEFAULT FALSE,

    -- Metadata
    last_seen_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    profile_completed_at    TIMESTAMPTZ,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

-- =============================================================================
-- OAUTH ACCOUNTS  (social login providers: Google, GitHub, Discord, etc.)
-- =============================================================================
CREATE TABLE IF NOT EXISTS oauth_accounts (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            VARCHAR(50) NOT NULL,      -- 'google' | 'github' | 'discord'
    provider_user_id    VARCHAR(255) NOT NULL,
    provider_email      CITEXT,
    access_token        TEXT,
    refresh_token       TEXT,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_oauth_provider UNIQUE (provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts(user_id);

-- =============================================================================
-- REFRESH TOKENS  (persistent login sessions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT        UNIQUE NOT NULL,   -- SHA-256 hash of the raw token
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id    ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);

-- =============================================================================
-- EMAIL VERIFICATION TOKENS
-- =============================================================================
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT        UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_verify_user_id ON email_verification_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_email_verify_token   ON email_verification_tokens(token);

-- =============================================================================
-- PASSWORD RESET TOKENS
-- =============================================================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT        UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pwd_reset_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_pwd_reset_token   ON password_reset_tokens(token);

-- =============================================================================
-- TRIGGERS  (auto-update updated_at)
-- =============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['users', 'user_profiles', 'oauth_accounts']
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS trg_%s_updated_at ON %s;
            CREATE TRIGGER trg_%s_updated_at
            BEFORE UPDATE ON %s
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        ', tbl, tbl, tbl, tbl);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- VIEWS  (public profiles — safe to expose to clients)
-- =============================================================================
CREATE OR REPLACE VIEW public_profiles AS
SELECT
    p.id,
    p.user_id,
    p.display_name,
    p.full_name,
    p.bio,
    p.avatar_url,
    p.banner_url,
    p.company,
    p.job_title,
    p.website,
    p.twitter_url,
    p.linkedin_url,
    p.github_url,
    p.country,
    p.created_at
FROM user_profiles p
WHERE p.is_public = TRUE;

-- =============================================================================
-- CLEANUP FUNCTION  (run periodically to purge expired tokens)
-- =============================================================================
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM refresh_tokens
        WHERE expires_at < NOW() OR revoked_at IS NOT NULL;

    DELETE FROM email_verification_tokens
        WHERE expires_at < NOW();

    DELETE FROM password_reset_tokens
        WHERE expires_at < NOW() OR used = TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Done!  Your schema is ready.
-- =============================================================================
\echo 'Schema setup complete.'
