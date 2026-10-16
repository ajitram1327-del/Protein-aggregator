-- ============================================================================
-- Migration: 0009_atomic_catalog_merge_and_ocr.sql
-- Description:
-- Enterprise-Grade Entity Resolution, Catalog Merging, and Nutrition Label OCR Cache
-- 1. catalog_redirect_aliases: Tracks legacy/duplicate UUIDs to master canonical UUIDs
-- 2. llm_resolution_cache: SHA-256 fingerprint cache for LLM disambiguations
-- 3. ocr_image_cache: Perceptual hash (pHash) cache for nutrition label OCR & spiking telemetry
-- 4. merge_duplicate_products_atomic: Transactional RPC executing atomic deduplication,
--    re-linking price listings, rolling up OCR metadata, updating lowest price, and deleting dupes.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Catalog Redirect Aliases Table
CREATE TABLE IF NOT EXISTS public.catalog_redirect_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('product', 'variant')),
    duplicate_id UUID NOT NULL,
    master_id UUID NOT NULL,
    redirect_reason TEXT DEFAULT 'dedupe_merge',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_redirect_duplicate UNIQUE (source_type, duplicate_id)
);

CREATE INDEX IF NOT EXISTS idx_redirect_duplicate ON public.catalog_redirect_aliases(duplicate_id);
CREATE INDEX IF NOT EXISTS idx_redirect_master ON public.catalog_redirect_aliases(master_id);

-- 2. LLM Resolution Cache Table
CREATE TABLE IF NOT EXISTS public.llm_resolution_cache (
    fingerprint CHAR(64) PRIMARY KEY, -- SHA-256(scraped_title || brand || weight_g || flavor)
    scraped_title TEXT NOT NULL,
    matched_variant_id UUID REFERENCES public.variants(id) ON DELETE SET NULL,
    matched_product_id UUID REFERENCES public.products(id) ON DELETE SET NULL,
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.90,
    model_provider VARCHAR(50) DEFAULT 'groq_llama3',
    raw_prompt TEXT,
    raw_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_cache_variant ON public.llm_resolution_cache(matched_variant_id);

-- 3. OCR Image Cache Table
CREATE TABLE IF NOT EXISTS public.ocr_image_cache (
    image_phash VARCHAR(64) PRIMARY KEY,
    image_url_normalized TEXT NOT NULL,
    serving_size_g NUMERIC(6, 2),
    servings_per_container INTEGER,
    energy_kcal NUMERIC(6, 2),
    protein_per_serving_g NUMERIC(5, 2),
    carbs_per_serving_g NUMERIC(5, 2),
    fat_per_serving_g NUMERIC(5, 2),
    sodium_mg NUMERIC(6, 2),
    leucine_g NUMERIC(5, 2),
    creatine_g NUMERIC(5, 2),
    glycine_g NUMERIC(5, 2),
    taurine_g NUMERIC(5, 2),
    raw_ingredients_text TEXT,
    amino_spiking_payload JSONB DEFAULT '{}',
    is_valid_physics BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ocr_cache_url ON public.ocr_image_cache(image_url_normalized);

-- 4. Atomic Catalog Merge RPC
CREATE OR REPLACE FUNCTION public.merge_duplicate_products_atomic(
    p_master_product_id UUID,
    p_duplicate_product_ids UUID[],
    p_variant_mappings JSONB, -- Array of objects: [{"duplicate_variant_id": "...", "target_variant_id": "..."}]
    p_ocr_nutrition_rollup JSONB DEFAULT NULL -- Optional OCR fields to update on master
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_dup_pid UUID;
    v_mapping JSONB;
    v_dup_vid UUID;
    v_target_vid UUID;
    v_relinked_count INT := 0;
    v_variants_deleted INT := 0;
    v_products_deleted INT := 0;
    v_pl RECORD;
BEGIN
    -- Ensure Master Product exists
    IF NOT EXISTS (SELECT 1 FROM public.products WHERE id = p_master_product_id) THEN
        RAISE EXCEPTION 'Master product % does not exist', p_master_product_id;
    END IF;

    -- 1. Roll up OCR nutrition & amino telemetry onto Master Product if provided
    IF p_ocr_nutrition_rollup IS NOT NULL AND p_ocr_nutrition_rollup <> '{}'::jsonb THEN
        UPDATE public.products
        SET 
            nutrition_serving_size_g = COALESCE(nutrition_serving_size_g, (p_ocr_nutrition_rollup->>'serving_size_g')::numeric),
            nutrition_protein_per_serving_g = COALESCE(nutrition_protein_per_serving_g, (p_ocr_nutrition_rollup->>'protein_per_serving_g')::numeric),
            nutrition_ingredients = COALESCE(nutrition_ingredients, p_ocr_nutrition_rollup->>'raw_ingredients_text')
        WHERE id = p_master_product_id;
    END IF;

    -- 2. Process Variant Mappings
    IF p_variant_mappings IS NOT NULL AND jsonb_array_length(p_variant_mappings) > 0 THEN
        FOR v_mapping IN SELECT * FROM jsonb_array_elements(p_variant_mappings)
        LOOP
            v_dup_vid := (v_mapping->>'duplicate_variant_id')::uuid;
            v_target_vid := (v_mapping->>'target_variant_id')::uuid;

            IF v_dup_vid IS NOT NULL AND v_target_vid IS NOT NULL AND v_dup_vid <> v_target_vid THEN
                -- Insert alias redirect record
                INSERT INTO public.catalog_redirect_aliases (source_type, duplicate_id, master_id, redirect_reason)
                VALUES ('variant', v_dup_vid, v_target_vid, 'merge_duplicate_products_atomic')
                ON CONFLICT (source_type, duplicate_id) 
                DO UPDATE SET master_id = EXCLUDED.master_id;

                -- Relink price_listings from duplicate variant to target variant
                FOR v_pl IN SELECT id, source FROM public.price_listings WHERE variant_id = v_dup_vid
                LOOP
                    -- Check if listing for same source already exists on target variant
                    IF EXISTS (SELECT 1 FROM public.price_listings WHERE variant_id = v_target_vid AND source = v_pl.source) THEN
                        -- Delete redundant duplicate listing to prevent conflict on (variant_id, source)
                        DELETE FROM public.price_listings WHERE id = v_pl.id;
                    ELSE
                        UPDATE public.price_listings
                        SET variant_id = v_target_vid, product_id = p_master_product_id
                        WHERE id = v_pl.id;
                        v_relinked_count := v_relinked_count + 1;
                    END IF;
                END LOOP;

                -- Also re-link offers table if present
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'offers') THEN
                    UPDATE public.offers
                    SET variant_id = v_target_vid
                    WHERE variant_id = v_dup_vid;
                END IF;

                -- Delete the unified duplicate variant
                DELETE FROM public.variants WHERE id = v_dup_vid;
                v_variants_deleted := v_variants_deleted + 1;
            END IF;
        END LOOP;
    END IF;

    -- 3. Any unmerged variants remaining on duplicate products: re-point to master product
    FOREACH v_dup_pid IN ARRAY p_duplicate_product_ids
    LOOP
        IF v_dup_pid <> p_master_product_id THEN
            -- Record product alias redirect
            INSERT INTO public.catalog_redirect_aliases (source_type, duplicate_id, master_id, redirect_reason)
            VALUES ('product', v_dup_pid, p_master_product_id, 'merge_duplicate_products_atomic')
            ON CONFLICT (source_type, duplicate_id)
            DO UPDATE SET master_id = EXCLUDED.master_id;

            -- Move remaining child variants to master product
            UPDATE public.variants
            SET product_id = p_master_product_id
            WHERE product_id = v_dup_pid;

            -- Ensure price_listings point to master product
            UPDATE public.price_listings
            SET product_id = p_master_product_id
            WHERE product_id = v_dup_pid;

            -- Delete the duplicate product shell
            DELETE FROM public.products WHERE id = v_dup_pid;
            v_products_deleted := v_products_deleted + 1;
        END IF;
    END LOOP;

    -- 4. Recompute lowest_price_inr across all master variants from active in_stock listings
    UPDATE public.variants v
    SET lowest_price_inr = sub.min_price
    FROM (
        SELECT variant_id, MIN(current_price_inr) as min_price
        FROM public.price_listings
        WHERE in_stock = true AND current_price_inr > 0
        GROUP BY variant_id
    ) sub
    WHERE v.product_id = p_master_product_id AND v.id = sub.variant_id;

    RETURN jsonb_build_object(
        'success', true,
        'master_product_id', p_master_product_id,
        'products_deleted', v_products_deleted,
        'variants_deleted', v_variants_deleted,
        'listings_relinked', v_relinked_count
    );
END;
$$;
