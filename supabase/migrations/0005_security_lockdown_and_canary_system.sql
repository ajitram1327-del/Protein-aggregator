-- ============================================================================
-- 0005_security_lockdown_and_canary_system.sql
-- ProteIndex Data Protection, RLS Lockdown, & Honeytoken Canary Alarm
-- ============================================================================

-- 1. Enable Row Level Security (RLS) across all ProteIndex tables
ALTER TABLE public.products                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.variants                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_listings             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offers                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_history              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comparison_snapshots       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scraper_rules              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.silo_catalogs              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences_analytics ENABLE ROW LEVEL SECURITY;

-- 2. Revoke default access on tables, sequences, routines from public roles
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM anon, authenticated;

-- 3. Explicitly deny all SELECT/INSERT/UPDATE/DELETE to public client roles
DROP POLICY IF EXISTS "Deny public products" ON public.products;
CREATE POLICY "Deny public products" ON public.products FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public variants" ON public.variants;
CREATE POLICY "Deny public variants" ON public.variants FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public price_listings" ON public.price_listings;
CREATE POLICY "Deny public price_listings" ON public.price_listings FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public offers" ON public.offers;
CREATE POLICY "Deny public offers" ON public.offers FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public price_history" ON public.price_history;
CREATE POLICY "Deny public price_history" ON public.price_history FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public comparison_snapshots" ON public.comparison_snapshots;
CREATE POLICY "Deny public comparison_snapshots" ON public.comparison_snapshots FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public scraper_rules" ON public.scraper_rules;
CREATE POLICY "Deny public scraper_rules" ON public.scraper_rules FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public silo_catalogs" ON public.silo_catalogs;
CREATE POLICY "Deny public silo_catalogs" ON public.silo_catalogs FOR ALL TO anon, authenticated USING (false);

DROP POLICY IF EXISTS "Deny public analytics" ON public.user_preferences_analytics;
CREATE POLICY "Deny public analytics" ON public.user_preferences_analytics FOR ALL TO anon, authenticated USING (false);

-- Note: In Supabase, the backend 'service_role' key automatically bypasses RLS,
-- allowing Python scrapers and Next.js server proxies full read/write operations.

-- 4. Honeypot & Canary Variant System
CREATE TABLE IF NOT EXISTS public.security_honeypot_logs (
    id BIGSERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    client_ip TEXT,
    user_agent TEXT,
    queried_variant_id UUID,
    sku_trapped TEXT,
    notes TEXT
);

-- Flag canary rows on variants table
ALTER TABLE public.variants
    ADD COLUMN IF NOT EXISTS is_canary BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_variants_is_canary ON public.variants(is_canary) WHERE is_canary = TRUE;

-- 5. Seed an invisible canary variant
DO $$
DECLARE
    sample_product_id UUID;
BEGIN
    SELECT id INTO sample_product_id FROM public.products LIMIT 1;
    IF sample_product_id IS NOT NULL THEN
        INSERT INTO public.variants (
            id,
            product_id,
            flavor,
            weight_grams,
            sku_id,
            is_canary,
            lowest_price_inr
        ) VALUES (
            'a0000000-0000-0000-0000-000000000001',
            sample_product_id,
            'Salted Butter Caramel Silk (Reserve)',
            908,
            'PRTX-CANARY-908-SBC',
            TRUE,
            2499.00
        ) ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;
