-- Comptes et sessions de l'espace personnel Ouaga Foncier.
-- Migration idempotente à exécuter une seule fois sur Neon.

CREATE TABLE IF NOT EXISTS public.app_users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT app_users_email_normalized
        CHECK (email = LOWER(TRIM(email)))
);

CREATE UNIQUE INDEX IF NOT EXISTS app_users_email_unique
    ON public.app_users (LOWER(email));

CREATE TABLE IF NOT EXISTS public.user_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id UUID NOT NULL
        REFERENCES public.app_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS user_sessions_user_id_idx
    ON public.user_sessions (user_id);

CREATE INDEX IF NOT EXISTS user_sessions_expires_at_idx
    ON public.user_sessions (expires_at);
