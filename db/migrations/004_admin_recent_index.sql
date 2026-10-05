-- Accélère l'affichage des annonces récentes dans l'espace administrateur.
CREATE INDEX IF NOT EXISTS annonces_preparees_collecte_idx
    ON public.annonces_preparees (premiere_collecte DESC, id DESC);
