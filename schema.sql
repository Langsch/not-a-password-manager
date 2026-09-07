-- not-a-password-manager — target schema. Alembic migrations are what create it.
-- PostgreSQL 18+ (uuidv7).
--
-- Secret fields are stored encrypted in the form v1.<nonce>.<content>,
-- AES-256-GCM, with the key coming from an environment variable.


CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TABLE users (
    id            SERIAL       PRIMARY KEY,
    external_id   UUID         NOT NULL UNIQUE DEFAULT uuidv7(),
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_email_lower_key ON users (lower(email));

CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON users FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION set_updated_at();


CREATE TABLE sessions (
    id                  SERIAL      PRIMARY KEY,
    token_hash          BYTEA       NOT NULL UNIQUE,
    user_id             INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at          TIMESTAMPTZ NOT NULL,
    absolute_expires_at TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT sessions_absolute_after_sliding
        CHECK (absolute_expires_at >= expires_at)
);

-- token_hash is the SHA-256 of the token; the token itself is never stored.
-- expires_at slides on every request, absolute_expires_at does not.
CREATE INDEX sessions_user_id_idx ON sessions (user_id);


CREATE TABLE items (
    id                 SERIAL       PRIMARY KEY,
    external_id        UUID         NOT NULL UNIQUE DEFAULT uuidv7(),
    user_id            INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name               VARCHAR(255) NOT NULL,
    username           VARCHAR(255),
    url                TEXT,
    password_encrypted TEXT         NOT NULL,
    notes_encrypted    TEXT,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT items_password_looks_encrypted
        CHECK (password_encrypted LIKE 'v1.%'),
    CONSTRAINT items_notes_look_encrypted
        CHECK (notes_encrypted IS NULL OR notes_encrypted LIKE 'v1.%')
);

-- Covers the owner filter and pagination's ORDER BY name, id.
CREATE INDEX items_user_id_name_id_idx ON items (user_id, name, id);

CREATE TRIGGER items_set_updated_at
    BEFORE UPDATE ON items FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION set_updated_at();
