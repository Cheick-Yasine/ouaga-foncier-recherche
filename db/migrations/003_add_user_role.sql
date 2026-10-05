-- Ajoute le rôle utilisateur attendu par l'authentification actuelle.
ALTER TABLE public.app_users
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

-- Garantit que le compte administrateur conserve les droits admin.
UPDATE public.app_users
SET role = 'admin'
WHERE LOWER(TRIM(email)) = 'admin';
