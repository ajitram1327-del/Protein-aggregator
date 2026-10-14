-- ============================================================================
-- Migration: 0003_proteindex_engine_delta_and_quarantine.sql
-- Description:
-- 1. Creates price_history cold timeseries table.
-- 2. Adds PostgreSQL AFTER UPDATE delta trigger on price_listings:
--    Records timeseries history ONLY when price or stock status physically changes.
-- 3. Creates unmatched_staging_queue with failure_reason for quarantine.
-- 4. Adds nutrition_audited_at and weight_extraction_method to variants.
-- 5. Configures autovacuum and optimal partial indexes.
-- ============================================================================

-- 1. Extend variants table with audit locking and extraction method metadata
ALTER TABLE variants
    ADD COLUMN IF NOT EXISTS nutrition_audited_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS weight_extraction_method TEXT DEFAULT 'title';

-- 2. Ensure price_listings has etag and last_modified_header
ALTER TABLE price_listings
    ADD COLUMN IF NOT EXISTS etag TEXT,
    ADD COLUMN IF NOT EXISTS last_modified_header TEXT,
    ADD COLUMN IF NOT EXISTS shipping TEXT DEFAULT 'standard';

-- 3. Autovacuum tuning for high-frequency write updates on price_listings
DO $$ BEGIN
    ALTER TABLE price_listings SET (
        autovacuum_vacuum_scale_factor = 0.05,
        autovacuum_vacuum_cost_limit = 500
    );
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 4. Cold State: Historical Audit Log (Delta Trigger)
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    platform_name VARCHAR(50) NOT NULL,
    price_inr NUMERIC(10, 2) NOT NULL,
    is_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexing for price history
CREATE INDEX IF NOT EXISTS idx_price_history_variant_date ON price_history (variant_id, recorded_at DESC);

-- Trigger Function: Only record when price or in_stock physically changes
CREATE OR REPLACE FUNCTION trg_fn_price_listings_audit()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.current_price_inr IS DISTINCT FROM NEW.current_price_inr) 
       OR (OLD.is_in_stock IS DISTINCT FROM NEW.is_in_stock)
       OR (OLD.price_inr IS DISTINCT FROM NEW.price_inr)
       OR (OLD.in_stock IS DISTINCT FROM NEW.in_stock) THEN
        INSERT INTO price_history (variant_id, platform_name, price_inr, is_in_stock, recorded_at)
        VALUES (
            NEW.variant_id, 
            COALESCE(NEW.platform_name, NEW.source, 'd2c'), 
            COALESCE(NEW.current_price_inr, NEW.price_inr, 0), 
            COALESCE(NEW.is_in_stock, NEW.in_stock, TRUE), 
            COALESCE(NEW.scraped_at, NOW())
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_price_listings_audit ON price_listings;
CREATE TRIGGER trg_price_listings_audit
AFTER UPDATE ON price_listings
FOR EACH ROW
EXECUTE FUNCTION trg_fn_price_listings_audit();

-- 5. Staging Quarantine: Unmatched Raw Scrapes with Explicit Failure Reason
CREATE TABLE IF NOT EXISTS unmatched_staging_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_name VARCHAR(50) NOT NULL,
    raw_title TEXT NOT NULL,
    raw_price NUMERIC(10, 2),
    raw_url TEXT NOT NULL,
    detected_brand TEXT,
    detected_weight_g INT,
    failure_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partial Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_listings_variant_cheapest_in_stock
ON price_listings (variant_id, current_price_inr ASC)
WHERE is_in_stock = TRUE;

CREATE INDEX IF NOT EXISTS idx_variants_nutrition_pending 
ON variants (id) 
WHERE nutrition_audited_at IS NULL;
