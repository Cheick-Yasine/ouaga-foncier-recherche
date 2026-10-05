-- Rôle administrateur pour l'espace « Interroger la base ».
ALTER TABLE public.app_users
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

ALTER TABLE public.app_users DROP CONSTRAINT IF EXISTS app_users_role_valid;
ALTER TABLE public.app_users
    ADD CONSTRAINT app_users_role_valid CHECK (role IN ('user', 'admin'));

CREATE INDEX IF NOT EXISTS app_users_role_idx ON public.app_users(role);

-- Compte administrateur initial : le mot de passe est conservé uniquement sous forme de hash scrypt.
INSERT INTO public.app_users (id, email, password_hash, role)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    'admin',
    'scrypt$16384$8$1$408eeb58fa10eda950e2089d0a787e77$350522dab3ef66213b2b163d0bf7b0de5081975f79375e195af07dd2293a3309',
    'admin'
)
ON CONFLICT (email) DO UPDATE SET role = 'admin';
