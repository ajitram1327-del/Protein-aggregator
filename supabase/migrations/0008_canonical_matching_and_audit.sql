-- ============================================================================
-- Migration: 0008_canonical_matching_and_audit.sql
-- Description:
-- Durable Schema Guardrails for Entity Matching and Deduplication
-- 1. Status and merge tracking on products (active | needs_review | merged).
-- 2. Audit trail table (match_events) recording every matching decision.
-- 3. Dynamic alias tables (product_aliases, flavour_aliases) for learning loop.
-- 4. Fast canonical view (v_canonical_catalog_offers) filtering out merged/unreviewed items.
-- ============================================================================

-- 1. Add status and merge tracking columns to products table
ALTER TABLE public.products 
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active' 
    CHECK (status IN ('active', 'needs_review', 'merged'));

ALTER TABLE public.products 
    ADD COLUMN IF NOT EXISTS merged_into UUID REFERENCES public.products(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_products_status_active 
    ON public.products(status) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_products_merged_into 
    ON public.products(merged_into) WHERE merged_into IS NOT NULL;

-- 2. Audit Trail for Matching Decisions
CREATE TABLE IF NOT EXISTS public.match_events (
    id BIGSERIAL PRIMARY KEY,
    listing_id UUID REFERENCES public.price_listings(id) ON DELETE CASCADE,
    from_variant_id UUID,
    to_variant_id UUID REFERENCES public.variants(id) ON DELETE SET NULL,
    method TEXT NOT NULL CHECK (method IN ('sticky', 'identifier', 'alias_rules', 'pg_trgm', 'llm_groq', 'llm_gemini', 'manual', 'unlink')),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    actor TEXT NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_match_events_listing ON public.match_events(listing_id);
CREATE INDEX IF NOT EXISTS idx_match_events_method ON public.match_events(method);
CREATE INDEX IF NOT EXISTS idx_match_events_created ON public.match_events(created_at DESC);

-- 3. Dynamic Product and Flavour Aliases (Self-Learning Feedback Loop)
CREATE TABLE IF NOT EXISTS public.product_aliases (
    id BIGSERIAL PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    raw_title_pattern TEXT NOT NULL UNIQUE,
    canonical_line_name TEXT NOT NULL,
    source TEXT DEFAULT 'auto',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_aliases_pattern ON public.product_aliases(raw_title_pattern);

CREATE TABLE IF NOT EXISTS public.flavour_aliases (
    id BIGSERIAL PRIMARY KEY,
    raw_flavor TEXT NOT NULL UNIQUE,
    canonical_flavor TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flavour_aliases_raw ON public.flavour_aliases(raw_flavor);

-- Seed common flavour aliases
INSERT INTO public.flavour_aliases (raw_flavor, canonical_flavor) VALUES
    ('double rich chocolate', 'chocolate'),
    ('rich chocolate', 'chocolate'),
    ('belgian chocolate', 'chocolate'),
    ('chocolate fudge', 'chocolate'),
    ('dark chocolate', 'chocolate'),
    ('creamy vanilla', 'vanilla'),
    ('french vanilla', 'vanilla'),
    ('vanilla ice cream', 'vanilla'),
    ('alphonso mango', 'mango'),
    ('cafe mocha', 'coffee'),
    ('cold coffee', 'coffee'),
    ('unflavoured', 'unflavored'),
    ('raw', 'unflavored'),
    ('zero flavor', 'unflavored'),
    ('cookies and cream', 'cookies_and_cream'),
    ('cookies & cream', 'cookies_and_cream'),
    ('cookies n cream', 'cookies_and_cream'),
    ('kesar pista', 'kesar_pista'),
    ('malai kulfi', 'kesar_pista')
ON CONFLICT (raw_flavor) DO NOTHING;

-- 4. Canonical Catalog Offers View (Shields UI from Merged or Pending Entities)
CREATE OR REPLACE VIEW public.v_canonical_catalog_offers AS
SELECT 
    p.id AS product_id,
    p.brand,
    p.base_name AS product_name,
    p.category_silo,
    p.protein_source,
    p.image_url,
    p.trust_score,
    p.is_fairy_dusted,
    p.lab_verified,
    p.lab_report_url,
    v.id AS variant_id,
    v.sku_id,
    v.flavor,
    v.weight_grams,
    v.lowest_price_inr,
    v.best_value_metric,
    v.calculated_purity_pct,
    pl.id AS price_listing_id,
    pl.source AS vendor_name,
    COALESCE(pl.current_price_inr, pl.price_inr) AS price_inr,
    COALESCE(pl.is_in_stock, pl.in_stock, true) AS is_in_stock,
    pl.seller_name,
    COALESCE(pl.listing_url, pl.source_url) AS store_url,
    pl.scraped_at
FROM public.products p
JOIN public.variants v ON v.product_id = p.id
LEFT JOIN public.price_listings pl ON pl.variant_id = v.id
WHERE p.status = 'active'
  AND p.merged_into IS NULL;

-- 5. RLS Lockdown on Audit and Aliases
ALTER TABLE public.match_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flavour_aliases ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public Read Flavour Aliases" ON public.flavour_aliases FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "Public Read Product Aliases" ON public.product_aliases FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "Deny Public Match Events" ON public.match_events FOR ALL TO anon, authenticated USING (false);
