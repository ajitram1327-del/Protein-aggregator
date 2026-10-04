-- Supabase Migration: 0001_initial_proteindx_schema.sql
-- Description: Sets up the normalized schema for ProteinDX products, variants, offers, and price history.

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand TEXT NOT NULL,
    base_name TEXT NOT NULL,
    category TEXT NOT NULL,
    protein_source TEXT NOT NULL,
    image_url TEXT,
    nutrition_serving_size_g NUMERIC,
    nutrition_protein_per_serving_g NUMERIC,
    nutrition_ingredients TEXT,
    nutrition_source TEXT DEFAULT 'extracted', -- 'extracted' or 'assumed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(brand, base_name)
);

CREATE TABLE variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    flavor TEXT NOT NULL,
    weight_grams NUMERIC NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(product_id, flavor, weight_grams)
);

CREATE TABLE offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    platform TEXT NOT NULL, -- e.g., 'brand_d2c', 'amazon', 'healthkart'
    url TEXT NOT NULL,
    current_price_inr NUMERIC NOT NULL,
    stock_status TEXT DEFAULT 'in_stock', -- 'in_stock', 'out_of_stock'
    raw_payload JSONB, -- For debugging parsing issues later
    is_valid BOOLEAN DEFAULT true, -- Bad rows go to review status
    last_scraped_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(variant_id, platform)
);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id UUID NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
    price_inr NUMERIC NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Analytics Table for Consumer Preferences (No PII)
CREATE TABLE user_preferences_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anonymous_session_id TEXT NOT NULL,
    brand_viewed TEXT,
    flavor_clicked TEXT,
    size_viewed_grams NUMERIC,
    protein_source_viewed TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Indexing for performance
CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_variants_product_id ON variants(product_id);
CREATE INDEX idx_offers_variant_id ON offers(variant_id);
CREATE INDEX idx_price_history_offer_id ON price_history(offer_id);
