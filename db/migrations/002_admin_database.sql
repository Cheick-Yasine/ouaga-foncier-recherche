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


CREATE TABLE IF NOT EXISTS public.admin_announcement_flags (
    announcement_id TEXT PRIMARY KEY,
    is_trashed BOOLEAN NOT NULL DEFAULT FALSE,
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    featured_priority INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS admin_flags_trash_idx ON public.admin_announcement_flags(is_trashed);
CREATE INDEX IF NOT EXISTS admin_flags_featured_idx ON public.admin_announcement_flags(is_featured, featured_priority DESC);

CREATE TABLE IF NOT EXISTS public.admin_added_annonces (
    id UUID PRIMARY KEY,
    url TEXT,
    date_publication TEXT,
    type_bien_normalise TEXT,
    quartier_zone TEXT,
    superficie_m2 NUMERIC,
    prix_fcfa NUMERIC,
    statut_document TEXT,
    contacts_whatsapp TEXT,
    resume_court TEXT,
    texte_nettoye TEXT NOT NULL,
    premiere_collecte TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES public.app_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS admin_added_annonces_collecte_idx ON public.admin_added_annonces(premiere_collecte DESC);
