-- ============================================================================
-- 0010_quarantine_and_purge_drift.sql
-- Native Supabase PL/pgSQL Database Cleanup & Quarantine Script
-- Identifies, isolates, logs, and purges historical mathematical/biological data drift.
-- ============================================================================

-- 1. Create the quarantine table if it doesn't already exist
CREATE TABLE IF NOT EXISTS public.staging_quarantine (
    id BIGSERIAL PRIMARY KEY,
    raw_title TEXT,
    raw_metadata JSONB,
    quarantine_reason TEXT,
    retailer_source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure RLS on staging_quarantine allows service role access
ALTER TABLE public.staging_quarantine ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Deny public staging_quarantine" ON public.staging_quarantine;
CREATE POLICY "Deny public staging_quarantine" ON public.staging_quarantine FOR ALL TO anon, authenticated USING (false);

-- 2. Execute an atomic transaction block to safely isolate and delete data drift rows
DO $$
DECLARE
    purged_row_record RECORD;
    count_purged INT := 0;
BEGIN
    RAISE NOTICE 'Beginning atomic audit trace on corrupted database records...';

    -- Loop through tracking variants where calculated metrics violate biological rules
    FOR purged_row_record IN 
        SELECT v.id, v.product_id, v.variant_hash, v.lowest_price_inr, v.raw_json_data, v.weight_grams, v.calculated_purity_pct
        FROM variants v
        WHERE 
            -- Catch explicit column inversion states (e.g. Clamped 100% or drift >= 96%)
            v.calculated_purity_pct >= 96.0
            OR (v.label_protein_per_serving_g > v.label_serving_size_g)
            OR (v.lowest_price_inr / NULLIF(v.weight_grams, 0)) < 0.60
    LOOP
        -- Log data drift parameters into the quarantine table before deletion
        INSERT INTO public.staging_quarantine (raw_title, raw_metadata, quarantine_reason, retailer_source)
        VALUES (
            'Historical Purged Variant: ID ' || purged_row_record.id,
            jsonb_build_object(
                'variant_hash', purged_row_record.variant_hash,
                'lowest_price_inr', purged_row_record.lowest_price_inr,
                'weight_grams', purged_row_record.weight_grams,
                'calculated_purity_pct', purged_row_record.calculated_purity_pct,
                'raw_json_data', purged_row_record.raw_json_data
            ),
            'Database Clean Script: Caught impossible mathematical or biological purity values.',
            'Supabase_Data_Migration_Engine'
        );
        
        -- Delete dependent price logs to maintain relational integrity
        DELETE FROM price_listings WHERE variant_id = purged_row_record.id;

        -- Delete the corrupted variant record from the core catalog table
        DELETE FROM variants WHERE id = purged_row_record.id;
        
        count_purged := count_purged + 1;
    END LOOP;

    RAISE NOTICE 'Data optimization complete. Cleaned % corrupted variant shells.', count_purged;
END $$;
