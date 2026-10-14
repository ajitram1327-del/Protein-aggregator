-- ============================================================================
-- Migration: 0004_create_silo_catalogs.sql
-- Description: Creates isolated separate catalog tables for Creatine, Mass Gainer,
-- and Pre-Workout performance silos, in strict adherence to PRD Section 3.
-- ============================================================================

-- 1. Creatine Master Catalog Table
CREATE TABLE IF NOT EXISTS creatine_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand TEXT NOT NULL,
    base_name TEXT NOT NULL,
    flavor TEXT NOT NULL DEFAULT 'unflavored',
    weight_grams NUMERIC(10, 2) NOT NULL,
    servings_count INTEGER NOT NULL DEFAULT 30,
    serving_size_g NUMERIC(5, 2) NOT NULL DEFAULT 3.0,
    creatine_per_serving_g NUMERIC(5, 2) NOT NULL DEFAULT 3.0,
    price_inr NUMERIC(10, 2) NOT NULL CHECK (price_inr >= 0),
    cost_per_g_creatine_inr NUMERIC(10, 2),
    platform TEXT NOT NULL DEFAULT 'd2c',
    listing_url TEXT,
    image_url TEXT,
    variant_hash CHAR(64) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_creatine_brand ON creatine_catalog(brand);
CREATE INDEX IF NOT EXISTS idx_creatine_best_val ON creatine_catalog(cost_per_g_creatine_inr ASC);

-- 2. Mass Gainer Master Catalog Table
CREATE TABLE IF NOT EXISTS mass_gainer_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand TEXT NOT NULL,
    base_name TEXT NOT NULL,
    flavor TEXT NOT NULL DEFAULT 'chocolate',
    weight_grams NUMERIC(10, 2) NOT NULL,
    servings_count INTEGER NOT NULL DEFAULT 15,
    serving_size_g NUMERIC(6, 2) NOT NULL DEFAULT 100.0,
    calories_per_serving NUMERIC(6, 2) NOT NULL DEFAULT 375.0,
    protein_per_serving_g NUMERIC(5, 2) NOT NULL DEFAULT 20.0,
    carbs_per_serving_g NUMERIC(6, 2) NOT NULL DEFAULT 70.0,
    carb_protein_ratio NUMERIC(5, 2) NOT NULL DEFAULT 3.5,
    price_inr NUMERIC(10, 2) NOT NULL CHECK (price_inr >= 0),
    cost_per_1000_kcal_inr NUMERIC(10, 2),
    platform TEXT NOT NULL DEFAULT 'd2c',
    listing_url TEXT,
    image_url TEXT,
    variant_hash CHAR(64) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gainer_brand ON mass_gainer_catalog(brand);
CREATE INDEX IF NOT EXISTS idx_gainer_best_val ON mass_gainer_catalog(cost_per_1000_kcal_inr ASC);

-- 3. Pre-Workout Master Catalog Table
CREATE TABLE IF NOT EXISTS pre_workout_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand TEXT NOT NULL,
    base_name TEXT NOT NULL,
    flavor TEXT NOT NULL DEFAULT 'fruit_punch',
    weight_grams NUMERIC(10, 2) NOT NULL,
    servings_count INTEGER NOT NULL DEFAULT 30,
    serving_size_g NUMERIC(5, 2) NOT NULL DEFAULT 8.0,
    caffeine_per_serving_mg NUMERIC(6, 2) NOT NULL DEFAULT 200.0,
    price_inr NUMERIC(10, 2) NOT NULL CHECK (price_inr >= 0),
    cost_per_scoop_inr NUMERIC(10, 2),
    platform TEXT NOT NULL DEFAULT 'd2c',
    listing_url TEXT,
    image_url TEXT,
    variant_hash CHAR(64) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_preworkout_brand ON pre_workout_catalog(brand);
CREATE INDEX IF NOT EXISTS idx_preworkout_best_val ON pre_workout_catalog(cost_per_scoop_inr ASC);
