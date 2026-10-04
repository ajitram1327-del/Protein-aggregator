-- Add Sneakopedia variant columns to price_listings
ALTER TABLE price_listings
ADD COLUMN IF NOT EXISTS flavor text,
ADD COLUMN IF NOT EXISTS weight text,
ADD COLUMN IF NOT EXISTS product_id uuid; -- Or integer depending on your schema

-- Add metadata column to products to hold the Phase 2 JSON blob
ALTER TABLE products
ADD COLUMN IF NOT EXISTS metadata jsonb;
