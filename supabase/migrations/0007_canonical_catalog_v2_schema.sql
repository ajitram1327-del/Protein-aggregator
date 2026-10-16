-- ============================================================================
-- Migration: 0007_canonical_catalog_v2_schema.sql
-- Description:
-- Proteindex v2.0 Phase 2 Core Architecture:
-- 1. P2-01 & P2-02: Canonical catalog schema (brands, product_lines, canonical_skus,
--    retailer_listings, nutrition_observations, current_offers) with partitioned
--    timeseries telemetry (offer_observations, price_history_timeseries).
-- 2. P2-03: Materialized metrics view (mv_sku_metrics) computing normalized economics
--    excluding invalid/quarantined nutrition observations.
-- 3. P2-04: Full-Text Search with pg_trgm, search_vector tsvector GIN indexes,
--    synonym mapping table (search_synonyms), and search_canonical_catalog RPC.
-- 4. P2-05: Entity resolution review queue (entity_resolution_staging).
-- 5. Strict RLS lockdown on raw scrape telemetry and review staging.
-- ============================================================================

-- 1. Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Brands Table
CREATE TABLE IF NOT EXISTS public.brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    country_of_origin TEXT DEFAULT 'IN',
    website_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brands_slug ON public.brands(slug);
CREATE INDEX IF NOT EXISTS idx_brands_name_trgm ON public.brands USING GIN (name gin_trgm_ops);

-- 3. Product Lines Table
CREATE TABLE IF NOT EXISTS public.product_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES public.brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    category_silo VARCHAR(50) NOT NULL DEFAULT 'protein',
    formulation TEXT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_brand_product_line_slug UNIQUE (brand_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_product_lines_brand ON public.product_lines(brand_id);
CREATE INDEX IF NOT EXISTS idx_product_lines_silo ON public.product_lines(category_silo);

-- 4. Canonical SKUs Table
CREATE TABLE IF NOT EXISTS public.canonical_skus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_line_id UUID REFERENCES public.product_lines(id) ON DELETE SET NULL,
    brand TEXT NOT NULL,
    name TEXT NOT NULL,
    sku_id TEXT NOT NULL UNIQUE,
    category_silo VARCHAR(50) NOT NULL DEFAULT 'protein',
    formulation TEXT,
    flavor TEXT NOT NULL DEFAULT 'unflavored',
    weight_g INTEGER NOT NULL CHECK (weight_g > 0),
    serving_size_g NUMERIC(6, 2),
    servings_per_container INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_canonical_skus_brand ON public.canonical_skus(brand);
CREATE INDEX IF NOT EXISTS idx_canonical_skus_silo ON public.canonical_skus(category_silo);
CREATE INDEX IF NOT EXISTS idx_canonical_skus_weight ON public.canonical_skus(weight_g);
CREATE INDEX IF NOT EXISTS idx_canonical_skus_name_trgm ON public.canonical_skus USING GIN (name gin_trgm_ops);

-- Full-Text Search TSVECTOR column on canonical_skus
ALTER TABLE public.canonical_skus 
    ADD COLUMN IF NOT EXISTS search_vector tsvector 
    GENERATED ALWAYS AS (
        to_tsvector('english', 
            COALESCE(brand, '') || ' ' || 
            COALESCE(name, '') || ' ' || 
            COALESCE(formulation, '') || ' ' || 
            COALESCE(flavor, '') || ' ' || 
            COALESCE(category_silo, '')
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_canonical_skus_search_vector ON public.canonical_skus USING GIN (search_vector);

-- 5. Nutrition Observations Table
CREATE TABLE IF NOT EXISTS public.nutrition_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_sku_id UUID REFERENCES public.canonical_skus(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES public.variants(id) ON DELETE CASCADE,
    protein_per_serving_g NUMERIC(5, 2),
    carbs_per_serving_g NUMERIC(5, 2),
    fat_per_serving_g NUMERIC(5, 2),
    calories_per_serving NUMERIC(6, 2),
    creatine_per_serving_g NUMERIC(5, 2),
    caffeine_per_serving_mg NUMERIC(6, 2),
    diaas_score NUMERIC(3, 2),
    diaas_basis TEXT,
    diaas_source_evidence TEXT,
    amino_acid_completeness_status TEXT DEFAULT 'unknown',
    quality_state TEXT NOT NULL DEFAULT 'pending_verification' CHECK (quality_state IN (
        'verified',
        'observed',
        'pending_verification',
        'stale',
        'quarantined',
        'unknown',
        'not_applicable'
    )),
    quarantine_reason TEXT,
    evidence_source TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nutrition_observations_sku ON public.nutrition_observations(canonical_sku_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_observations_variant ON public.nutrition_observations(variant_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_observations_quality ON public.nutrition_observations(quality_state);

-- 6. Retailer Listings Table
CREATE TABLE IF NOT EXISTS public.retailer_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_sku_id UUID REFERENCES public.canonical_skus(id) ON DELETE SET NULL,
    variant_id UUID REFERENCES public.variants(id) ON DELETE CASCADE,
    retailer TEXT NOT NULL,
    product_url TEXT NOT NULL,
    external_sku_id TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_retailer_product_url UNIQUE (retailer, product_url)
);

CREATE INDEX IF NOT EXISTS idx_retailer_listings_sku ON public.retailer_listings(canonical_sku_id);
CREATE INDEX IF NOT EXISTS idx_retailer_listings_variant ON public.retailer_listings(variant_id);
CREATE INDEX IF NOT EXISTS idx_retailer_listings_retailer ON public.retailer_listings(retailer);

-- 7. Partitioned Telemetry: Offer Observations (Monthly Range Partitioning)
CREATE TABLE IF NOT EXISTS public.offer_observations (
    id UUID DEFAULT gen_random_uuid(),
    listing_id UUID,
    variant_id UUID,
    canonical_sku_id UUID,
    price_inr NUMERIC(10, 2) NOT NULL CHECK (price_inr >= 0),
    is_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    stock_status TEXT DEFAULT 'in_stock',
    seller_name TEXT,
    is_authorized_seller BOOLEAN DEFAULT TRUE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, observed_at)
) PARTITION BY RANGE (observed_at);

-- Monthly partitions for 2026 and 2027
CREATE TABLE IF NOT EXISTS public.offer_observations_2026_09 PARTITION OF public.offer_observations
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.offer_observations_2026_10 PARTITION OF public.offer_observations
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.offer_observations_2026_11 PARTITION OF public.offer_observations
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.offer_observations_2026_12 PARTITION OF public.offer_observations
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.offer_observations_2027_01 PARTITION OF public.offer_observations
    FOR VALUES FROM ('2027-01-01 00:00:00+00') TO ('2027-02-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.offer_observations_default PARTITION OF public.offer_observations
    DEFAULT;

CREATE INDEX IF NOT EXISTS idx_offer_observations_variant ON public.offer_observations(variant_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_offer_observations_sku ON public.offer_observations(canonical_sku_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_offer_observations_price ON public.offer_observations(price_inr);

-- 8. Partitioned Price History Timeseries
CREATE TABLE IF NOT EXISTS public.price_history_timeseries (
    id BIGSERIAL,
    variant_id UUID NOT NULL,
    platform_name VARCHAR(50) NOT NULL,
    price_inr NUMERIC(10, 2) NOT NULL,
    is_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

CREATE TABLE IF NOT EXISTS public.price_history_2026_10 PARTITION OF public.price_history_timeseries
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.price_history_2026_11 PARTITION OF public.price_history_timeseries
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.price_history_2026_12 PARTITION OF public.price_history_timeseries
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.price_history_2027_01 PARTITION OF public.price_history_timeseries
    FOR VALUES FROM ('2027-01-01 00:00:00+00') TO ('2027-02-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS public.price_history_default PARTITION OF public.price_history_timeseries
    DEFAULT;

CREATE INDEX IF NOT EXISTS idx_price_history_ts_variant_date ON public.price_history_timeseries (variant_id, recorded_at DESC);

-- 9. Fast Read Model: Current Active Offers
CREATE OR REPLACE VIEW public.current_offers AS
SELECT DISTINCT ON (COALESCE(listing_id, id))
    id,
    listing_id,
    variant_id,
    canonical_sku_id,
    price_inr,
    is_in_stock,
    stock_status,
    seller_name,
    is_authorized_seller,
    observed_at
FROM public.offer_observations
ORDER BY COALESCE(listing_id, id), observed_at DESC;

-- 10. P2-03: Materialized Metrics View (Excluding Quarantined / Invalid Data)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_sku_metrics AS
WITH latest_valid_nutrition AS (
    SELECT DISTINCT ON (COALESCE(canonical_sku_id, variant_id))
        id,
        canonical_sku_id,
        variant_id,
        protein_per_serving_g,
        carbs_per_serving_g,
        fat_per_serving_g,
        calories_per_serving,
        creatine_per_serving_g,
        caffeine_per_serving_mg,
        diaas_score,
        diaas_basis,
        quality_state,
        observed_at
    FROM public.nutrition_observations
    WHERE quality_state IN ('verified', 'observed')
      AND protein_per_serving_g > 0
    ORDER BY COALESCE(canonical_sku_id, variant_id), observed_at DESC
),
cheapest_offers AS (
    SELECT 
        COALESCE(canonical_sku_id, variant_id) as target_id,
        variant_id,
        canonical_sku_id,
        MIN(price_inr) FILTER (WHERE is_in_stock = TRUE AND price_inr > 0) AS min_price_inr,
        COUNT(DISTINCT seller_name) AS seller_count,
        MAX(observed_at) AS last_observed_at
    FROM public.offer_observations
    GROUP BY COALESCE(canonical_sku_id, variant_id), variant_id, canonical_sku_id
)
SELECT 
    s.id AS canonical_sku_id,
    v.id AS variant_id,
    s.brand,
    s.name,
    s.sku_id,
    s.category_silo,
    s.flavor,
    s.weight_g,
    s.serving_size_g,
    s.servings_per_container,
    co.min_price_inr AS lowest_price_inr,
    co.seller_count,
    co.last_observed_at,
    n.quality_state AS nutrition_quality_state,
    n.protein_per_serving_g,
    n.diaas_score,
    -- Cost per gram bioavailable protein
    CASE 
        WHEN s.category_silo = 'protein' 
             AND co.min_price_inr > 0 
             AND n.protein_per_serving_g > 0 
             AND COALESCE(s.servings_per_container, 0) > 0 THEN
            ROUND(
                (co.min_price_inr / (s.servings_per_container * n.protein_per_serving_g * COALESCE(n.diaas_score, 1.0)))::numeric, 
                2
            )
        ELSE NULL 
    END AS effective_cost_per_g_protein,
    -- Cost per 3g creatine dose
    CASE 
        WHEN s.category_silo = 'creatine' 
             AND co.min_price_inr > 0 
             AND s.weight_g > 0 THEN
            ROUND(
                (co.min_price_inr / (s.weight_g / 3.0))::numeric, 
                2
            )
        ELSE NULL 
    END AS cost_per_3g_creatine,
    -- Cost per 1,000 kcal for mass gainers
    CASE 
        WHEN s.category_silo = 'mass_gainers' 
             AND co.min_price_inr > 0 
             AND COALESCE(n.calories_per_serving, 0) > 0 
             AND COALESCE(s.servings_per_container, 0) > 0 THEN
            ROUND(
                (co.min_price_inr / ((s.servings_per_container * n.calories_per_serving) / 1000.0))::numeric, 
                2
            )
        ELSE NULL 
    END AS cost_per_1000_kcal,
    -- Purity %
    CASE 
        WHEN n.protein_per_serving_g > 0 AND COALESCE(s.serving_size_g, 0) > 0 THEN
            LEAST(100.0, ROUND(((n.protein_per_serving_g / s.serving_size_g) * 100.0)::numeric, 1))
        ELSE NULL 
    END AS purity_pct
FROM public.canonical_skus s
LEFT JOIN public.variants v ON v.sku_id = s.sku_id
LEFT JOIN cheapest_offers co ON co.canonical_sku_id = s.id OR co.variant_id = v.id
LEFT JOIN latest_valid_nutrition n ON n.canonical_sku_id = s.id OR n.variant_id = v.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_sku_metrics_sku_id ON public.mv_sku_metrics(canonical_sku_id);
CREATE INDEX IF NOT EXISTS idx_mv_sku_metrics_silo ON public.mv_sku_metrics(category_silo);
CREATE INDEX IF NOT EXISTS idx_mv_sku_metrics_cost_protein ON public.mv_sku_metrics(effective_cost_per_g_protein ASC NULLS LAST);

-- 11. P2-04: Synonym Mapping & Full Text Search RPC
CREATE TABLE IF NOT EXISTS public.search_synonyms (
    term TEXT PRIMARY KEY,
    expanded_terms TEXT[] NOT NULL
);

INSERT INTO public.search_synonyms (term, expanded_terms) VALUES
    ('creatine mono', ARRAY['creatine', 'monohydrate', 'creapure']),
    ('creatine monohydrate', ARRAY['creatine', 'mono', 'creapure']),
    ('whey iso', ARRAY['whey', 'isolate', 'iso']),
    ('whey isolate', ARRAY['whey', 'iso', 'isolate']),
    ('raw whey', ARRAY['raw', 'unflavored', 'concentrate']),
    ('mass gainer', ARRAY['gainer', 'carbs', 'calories', 'weight gainer']),
    ('pre workout', ARRAY['preworkout', 'caffeine', 'pump', 'energy']),
    ('eaa', ARRAY['essential amino', 'amino acids', 'bcaa']),
    ('bcaa', ARRAY['branched chain', 'amino', 'eaa'])
ON CONFLICT (term) DO NOTHING;

CREATE OR REPLACE FUNCTION public.search_canonical_catalog(
    query_text TEXT,
    silo_filter TEXT DEFAULT NULL,
    limit_val INT DEFAULT 20
)
RETURNS TABLE (
    sku_id TEXT,
    brand TEXT,
    name TEXT,
    category_silo VARCHAR(50),
    flavor TEXT,
    weight_g INT,
    similarity_score REAL
) AS $$
DECLARE
    clean_query TEXT := trim(lower(query_text));
    expanded_query TEXT := clean_query;
BEGIN
    SELECT array_to_string(expanded_terms, ' ') INTO expanded_query 
    FROM public.search_synonyms 
    WHERE term = clean_query;

    IF expanded_query IS NULL THEN
        expanded_query := clean_query;
    END IF;

    RETURN QUERY
    SELECT 
        s.sku_id,
        s.brand,
        s.name,
        s.category_silo,
        s.flavor,
        s.weight_g,
        similarity(s.brand || ' ' || s.name || ' ' || s.flavor, clean_query) AS similarity_score
    FROM public.canonical_skus s
    WHERE (silo_filter IS NULL OR s.category_silo = silo_filter)
      AND (
          s.search_vector @@ plainto_tsquery('english', expanded_query)
          OR similarity(s.brand || ' ' || s.name || ' ' || s.flavor, clean_query) > 0.2
      )
    ORDER BY similarity_score DESC
    LIMIT limit_val;
END;
$$ LANGUAGE plpgsql STABLE;

-- 12. P2-05: Entity Resolution Staging & Review Queue
CREATE TABLE IF NOT EXISTS public.entity_resolution_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_listing_id UUID,
    raw_title TEXT NOT NULL,
    raw_brand TEXT,
    raw_weight_g INT,
    raw_silo TEXT,
    candidate_canonical_sku_id UUID REFERENCES public.canonical_skus(id),
    confidence_score NUMERIC(5, 4) NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (resolution_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entity_staging_status ON public.entity_resolution_staging(resolution_status);

-- 13. Row-Level Security (RLS) Lockdown
ALTER TABLE public.brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.canonical_skus ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nutrition_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.retailer_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offer_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_history_timeseries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_synonyms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.entity_resolution_staging ENABLE ROW LEVEL SECURITY;

-- Public read access to verified catalog entities
CREATE POLICY "Public Read Brands" ON public.brands FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "Public Read Product Lines" ON public.product_lines FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "Public Read Canonical SKUs" ON public.canonical_skus FOR SELECT TO anon, authenticated USING (is_active = true);
CREATE POLICY "Public Read Nutrition Observations" ON public.nutrition_observations FOR SELECT TO anon, authenticated USING (quality_state IN ('verified', 'observed'));
CREATE POLICY "Public Read Retailer Listings" ON public.retailer_listings FOR SELECT TO anon, authenticated USING (is_active = true);
CREATE POLICY "Public Read Search Synonyms" ON public.search_synonyms FOR SELECT TO anon, authenticated USING (true);

-- Deny public access to internal staging queues and raw high-frequency observations
CREATE POLICY "Deny Public Entity Staging" ON public.entity_resolution_staging FOR ALL TO anon, authenticated USING (false);
CREATE POLICY "Deny Public Offer Observations" ON public.offer_observations FOR ALL TO anon, authenticated USING (false);
CREATE POLICY "Deny Public Price History Timeseries" ON public.price_history_timeseries FOR ALL TO anon, authenticated USING (false);
