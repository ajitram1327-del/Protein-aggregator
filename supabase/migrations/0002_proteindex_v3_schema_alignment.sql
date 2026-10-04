-- Supabase Migration: 0002_proteindex_v3_schema_alignment.sql
-- Description: Extends 0001 schema to align with Proteindex Master PRD (v2.1 & v3)
-- Strict adherence to 'Existing Infrastructure First' & Regression Rule:
-- 1. Preserves all existing tables (products, variants, offers, price_history, user_preferences_analytics)
-- 2. Extends products & variants with analytical, trust, and vision fields
-- 3. Creates price_listings with dual-write synchronization triggers to offers table
-- 4. Creates comparison_snapshots and scraper_rules tables
-- 5. Hardened with comprehensive indexes on category_silo, variant_id, variant_hash, and foreign keys

-- 1. Enable pgcrypto if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Extend products table with PRD compliance columns
ALTER TABLE products 
    ADD COLUMN IF NOT EXISTS category_silo VARCHAR(50) DEFAULT 'protein',
    ADD COLUMN IF NOT EXISTS baseline_diaas_score NUMERIC(3, 2) DEFAULT 1.00,
    ADD COLUMN IF NOT EXISTS fssai_license_number VARCHAR(14),
    ADD COLUMN IF NOT EXISTS fssai_warning_active BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fssai_last_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_fairy_dusted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fairy_dusting_flags TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS trust_score NUMERIC NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS lab_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS lab_report_url TEXT;

-- Indexing for products silo queries and trust score
CREATE INDEX IF NOT EXISTS idx_products_category_silo ON products(category_silo);
CREATE INDEX IF NOT EXISTS idx_products_silo_brand ON products(category_silo, brand);
CREATE INDEX IF NOT EXISTS idx_products_trust_score ON products(trust_score DESC);

-- 3. Extend variants table with deterministic hash & optical extraction columns
ALTER TABLE variants
    ADD COLUMN IF NOT EXISTS variant_hash CHAR(64),
    ADD COLUMN IF NOT EXISTS sku_id TEXT,
    ADD COLUMN IF NOT EXISTS lowest_price_inr NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS servings_count INTEGER,
    ADD COLUMN IF NOT EXISTS best_value_metric NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS raw_json_data TEXT,
    ADD COLUMN IF NOT EXISTS authenticity_score NUMERIC(5, 2) DEFAULT 100.0,
    ADD COLUMN IF NOT EXISTS has_bot_reviews BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS label_serving_size_g NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS label_protein_per_serving_g NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS label_total_servings INTEGER,
    ADD COLUMN IF NOT EXISTS calculated_purity_pct NUMERIC(5, 2),
    ADD COLUMN IF NOT EXISTS ocr_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS ocr_image_url TEXT,
    ADD COLUMN IF NOT EXISTS has_digestive_enzymes BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS detected_enzymes TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS is_lactose_free BOOLEAN NOT NULL DEFAULT FALSE;

-- Ensure sku_id and variant_hash have unique indexes when populated
CREATE UNIQUE INDEX IF NOT EXISTS idx_variants_sku_id ON variants(sku_id) WHERE sku_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_variants_variant_hash ON variants(variant_hash) WHERE variant_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_variants_best_value ON variants(best_value_metric ASC) WHERE best_value_metric IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_variants_lowest_price ON variants(lowest_price_inr ASC) WHERE lowest_price_inr IS NOT NULL;

-- 4. Create price_listings table (PRD V2/V3 & Scrapling Engine target)
CREATE TABLE IF NOT EXISTS price_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    platform_name VARCHAR(50) DEFAULT 'd2c_brand',
    source TEXT DEFAULT 'd2c_brand',
    listing_url TEXT,
    source_url TEXT,
    current_price_inr NUMERIC(10, 2) NOT NULL DEFAULT 0.0 CHECK (current_price_inr >= 0),
    price_inr NUMERIC(10, 2) NOT NULL DEFAULT 0.0 CHECK (price_inr >= 0),
    is_in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    seller_name TEXT DEFAULT '',
    is_authorized_seller BOOLEAN NOT NULL DEFAULT TRUE,
    raw_payload JSONB NOT NULL DEFAULT '{}',
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_variant_source UNIQUE(variant_id, source)
);

-- Indexing for price listings
CREATE INDEX IF NOT EXISTS idx_price_listings_variant_id ON price_listings(variant_id);
CREATE INDEX IF NOT EXISTS idx_price_listings_variant_price ON price_listings(variant_id, current_price_inr ASC);
CREATE INDEX IF NOT EXISTS idx_price_listings_variant_stock ON price_listings(variant_id, in_stock);
CREATE INDEX IF NOT EXISTS idx_price_listings_source ON price_listings(source);

-- 5. Create comparison_snapshots table (PRD Section 11)
CREATE TABLE IF NOT EXISTS comparison_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_ids UUID[] NOT NULL CHECK (array_length(variant_ids, 1) BETWEEN 2 AND 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '90 days')
);

CREATE INDEX IF NOT EXISTS idx_snapshots_expiry ON comparison_snapshots(expires_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_variant_ids ON comparison_snapshots USING GIN (variant_ids);

-- 6. Create scraper_rules table for self-healing selector caching (PRD Section 9.3)
CREATE TABLE IF NOT EXISTS scraper_rules (
    platform_name VARCHAR(50) PRIMARY KEY,
    price_selector TEXT NOT NULL,
    title_selector TEXT NOT NULL,
    out_of_stock_selector TEXT,
    last_healed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Create independent_lab_tests table (PRD Section 10.5)
CREATE TABLE IF NOT EXISTS independent_lab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    lab_name VARCHAR(100) NOT NULL,
    batch_number VARCHAR(100),
    protein_tested_yield_pct NUMERIC(5, 2),
    heavy_metal_lead_ppm NUMERIC(5, 2),
    heavy_metal_arsenic_ppm NUMERIC(5, 2),
    passed_audit BOOLEAN NOT NULL DEFAULT TRUE,
    report_url TEXT,
    tested_at DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_independent_lab_tests_product_id ON independent_lab_tests(product_id);

-- 8. Backwards-compatibility synchronization trigger:
-- Automatically syncs writes & deletes between legacy 'offers' and PRD 'price_listings'
CREATE OR REPLACE FUNCTION sync_offers_to_price_listings()
RETURNS TRIGGER AS $$
DECLARE
    safe_price NUMERIC(10, 2);
    is_available BOOLEAN;
    safe_platform TEXT;
    safe_url TEXT;
    safe_scraped_at TIMESTAMPTZ;
BEGIN
    -- Handle row deletions from legacy offers
    IF TG_OP = 'DELETE' THEN
        DELETE FROM price_listings 
        WHERE variant_id = OLD.variant_id 
          AND (source = OLD.platform OR platform_name = OLD.platform);

        -- Recompute lowest price from remaining active in-stock listings
        UPDATE variants
        SET lowest_price_inr = (
            SELECT MIN(current_price_inr)
            FROM price_listings
            WHERE variant_id = OLD.variant_id
              AND is_in_stock = TRUE
              AND current_price_inr > 0
        )
        WHERE id = OLD.variant_id;

        RETURN OLD;
    END IF;

    IF NEW.variant_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Clamp price defensively to satisfy CHECK (current_price_inr >= 0)
    safe_price := GREATEST(COALESCE(NEW.current_price_inr, 0.0), 0.0);

    -- Stock status check: must be in_stock, valid, and positive price
    is_available := (
        LOWER(COALESCE(NEW.stock_status, '')) = 'in_stock'
        AND COALESCE(NEW.is_valid, TRUE) IS TRUE
        AND safe_price > 0.0
    );

    safe_platform := COALESCE(NULLIF(TRIM(NEW.platform), ''), 'd2c_brand');
    safe_url := COALESCE(NEW.url, '');
    safe_scraped_at := COALESCE(NEW.last_scraped_at, NOW());

    INSERT INTO price_listings (
        variant_id,
        platform_name,
        source,
        listing_url,
        source_url,
        current_price_inr,
        price_inr,
        is_in_stock,
        in_stock,
        raw_payload,
        scraped_at
    )
    VALUES (
        NEW.variant_id,
        safe_platform,
        safe_platform,
        safe_url,
        safe_url,
        safe_price,
        safe_price,
        is_available,
        is_available,
        COALESCE(NEW.raw_payload, '{}'::jsonb),
        safe_scraped_at
    )
    ON CONFLICT (variant_id, source)
    DO UPDATE SET
        current_price_inr = EXCLUDED.current_price_inr,
        price_inr = EXCLUDED.price_inr,
        is_in_stock = EXCLUDED.is_in_stock,
        in_stock = EXCLUDED.in_stock,
        listing_url = EXCLUDED.listing_url,
        source_url = EXCLUDED.source_url,
        raw_payload = EXCLUDED.raw_payload,
        scraped_at = EXCLUDED.scraped_at;

    -- Synchronize lowest_price_inr on variants table
    IF is_available AND safe_price > 0.0 THEN
        UPDATE variants
        SET lowest_price_inr = LEAST(
            COALESCE(lowest_price_inr, safe_price),
            (
                SELECT COALESCE(MIN(current_price_inr), safe_price)
                FROM price_listings
                WHERE variant_id = NEW.variant_id
                  AND is_in_stock = TRUE
                  AND current_price_inr > 0
            )
        )
        WHERE id = NEW.variant_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_offers_to_price_listings ON offers;
CREATE TRIGGER trg_sync_offers_to_price_listings
AFTER INSERT OR UPDATE OR DELETE ON offers
FOR EACH ROW
EXECUTE FUNCTION sync_offers_to_price_listings();
