-- Snapshot quotidien des prix médians au m² par quartier.
-- Une ligne par quartier et par jour ; aucun détail d'annonce ni contact n'est stocké.
CREATE TABLE IF NOT EXISTS public.market_neighborhood_price_daily (
    snapshot_date date NOT NULL,
    neighborhood_key text NOT NULL,
    neighborhood_name text NOT NULL,
    median_price_m2_fcfa numeric(18,2),
    listing_count integer NOT NULL DEFAULT 0,
    priced_listing_count integer NOT NULL DEFAULT 0,
    computed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_date, neighborhood_key),
    CHECK (listing_count >= 0),
    CHECK (priced_listing_count >= 0),
    CHECK (priced_listing_count <= listing_count),
    CHECK (median_price_m2_fcfa IS NULL OR median_price_m2_fcfa >= 0)
);
CREATE INDEX IF NOT EXISTS idx_market_neighborhood_price_daily_latest
    ON public.market_neighborhood_price_daily (snapshot_date DESC, neighborhood_name);
