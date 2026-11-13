-- Snapshot quotidien des prix médians au m² par quartier.
-- Un enregistrement par quartier et par date ; aucune donnée d'annonce brute.
CREATE TABLE IF NOT EXISTS public.market_neighborhood_daily_prices (
    snapshot_date date NOT NULL,
    neighborhood_key text NOT NULL,
    neighborhood_name text NOT NULL,
    median_price_m2 numeric(18, 2),
    listing_count integer NOT NULL DEFAULT 0,
    calculated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT market_neighborhood_daily_prices_pk
        PRIMARY KEY (snapshot_date, neighborhood_key),
    CONSTRAINT market_neighborhood_daily_prices_count_nonnegative
        CHECK (listing_count >= 0),
    CONSTRAINT market_neighborhood_daily_prices_median_positive
        CHECK (median_price_m2 IS NULL OR median_price_m2 > 0)
);

CREATE INDEX IF NOT EXISTS market_neighborhood_daily_prices_latest_idx
    ON public.market_neighborhood_daily_prices (snapshot_date DESC, neighborhood_name);
