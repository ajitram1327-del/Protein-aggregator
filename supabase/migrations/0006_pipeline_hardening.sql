-- ============================================================================
-- 0006_pipeline_hardening.sql
-- Production Ingestion Hardening: Quarantine Buffer, Delta Triggers, Indices
-- ============================================================================

-- 1. Create Quarantine Buffer for Combo Bundles & Unmatched Scrapes
CREATE TABLE IF NOT EXISTS public.staging_quarantine (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    platform TEXT NOT NULL,
    brand_hint TEXT,
    raw_title TEXT NOT NULL,
    raw_price NUMERIC(10, 2),
    raw_url TEXT,
    detected_weight_g INTEGER,
    failure_category TEXT NOT NULL CHECK (failure_category IN (
        'COMBO_BUNDLE',
        'ACCESSORY_OR_GEAR',
        'UNRESOLVABLE_WEIGHT',
        'FORMULATION_MISMATCH',
        'AMINO_SPIKED',
        'SCRAPER_PARSE_ERROR'
    )),
    details JSONB DEFAULT '{}'::jsonb,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_staging_quarantine_category ON public.staging_quarantine(failure_category);
CREATE INDEX IF NOT EXISTS idx_staging_quarantine_created ON public.staging_quarantine(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_staging_quarantine_resolved ON public.staging_quarantine(is_resolved) WHERE is_resolved = FALSE;

-- 2. Performance Indexes for Ingestion Fast-Paths
CREATE INDEX IF NOT EXISTS idx_variants_hash_lookup ON public.variants(variant_hash);
CREATE INDEX IF NOT EXISTS idx_products_brand_basename ON public.products(brand, base_name);
CREATE INDEX IF NOT EXISTS idx_price_listings_variant_source ON public.price_listings(variant_id, source);

-- 3. Optimized Delta Trigger Function for price_history
-- Only logs a row when the price or stock status genuinely changes.
-- Prevents 95% table bloat from routine continuous scraping polling cycles.
CREATE OR REPLACE FUNCTION public.fn_log_price_delta()
RETURNS TRIGGER AS $$
BEGIN
    -- On INSERT or when price/stock actually changed on UPDATE
    IF (TG_OP = 'INSERT') OR 
       (TG_OP = 'UPDATE' AND (OLD.price_inr IS DISTINCT FROM NEW.price_inr OR OLD.is_in_stock IS DISTINCT FROM NEW.is_in_stock)) THEN
        
        INSERT INTO public.price_history (
            variant_id,
            price_inr,
            in_stock,
            recorded_at
        ) VALUES (
            NEW.variant_id,
            COALESCE(NEW.price_inr, 0.0),
            COALESCE(NEW.is_in_stock, TRUE),
            NOW()
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Bind trigger to price_listings table
DROP TRIGGER IF EXISTS trg_price_listings_delta_log ON public.price_listings;
CREATE TRIGGER trg_price_listings_delta_log
AFTER INSERT OR UPDATE ON public.price_listings
FOR EACH ROW
EXECUTE FUNCTION public.fn_log_price_delta();

-- 4. Enable RLS on new staging_quarantine table and deny public access
ALTER TABLE public.staging_quarantine ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Deny public staging_quarantine" ON public.staging_quarantine;
CREATE POLICY "Deny public staging_quarantine" ON public.staging_quarantine FOR ALL TO anon, authenticated USING (false);
