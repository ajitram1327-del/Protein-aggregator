import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);

async function migrate() {
    console.log('Running migration: Add multi-source pricing...');

    // Add source-specific price columns to variants
    const migrations = [
        `ALTER TABLE variants ADD COLUMN IF NOT EXISTS d2c_price_inr NUMERIC(10,2)`,
        `ALTER TABLE variants ADD COLUMN IF NOT EXISTS healthkart_price_inr NUMERIC(10,2)`,
        `ALTER TABLE variants ADD COLUMN IF NOT EXISTS amazon_price_inr NUMERIC(10,2)`,
        `ALTER TABLE variants ADD COLUMN IF NOT EXISTS flipkart_price_inr NUMERIC(10,2)`,
        `CREATE TABLE IF NOT EXISTS price_listings (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            source_url TEXT,
            price_inr NUMERIC(10,2) NOT NULL,
            in_stock BOOLEAN DEFAULT true,
            scraped_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(variant_id, source)
        )`,
        `CREATE INDEX IF NOT EXISTS idx_price_listings_variant ON price_listings(variant_id)`,
        `CREATE INDEX IF NOT EXISTS idx_price_listings_source ON price_listings(source)`,
    ];

    for (const sql of migrations) {
        const res = await fetch(`${process.env.SUPABASE_URL}/rest/v1/`, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_KEY,
                'Authorization': `Bearer ${process.env.SUPABASE_KEY}`,
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
        });

        // Use the pg-meta endpoint instead
        const r2 = await fetch(`${process.env.SUPABASE_URL}/rest/v1/rpc/query`, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_KEY,
                'Authorization': `Bearer ${process.env.SUPABASE_KEY}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: sql })
        });
        console.log(`[${r2.status}] ${sql.substring(0, 60)}...`);
    }

    // Test if price_listings exists
    const { data, error } = await supabase.from('price_listings').select('id').limit(1);
    if (error && error.code === '42P01') {
        console.log('\n[!] price_listings table does not exist yet.');
        console.log('Please run this SQL in your Supabase Dashboard > SQL Editor:\n');
        console.log(`
ALTER TABLE variants ADD COLUMN IF NOT EXISTS d2c_price_inr NUMERIC(10,2);
ALTER TABLE variants ADD COLUMN IF NOT EXISTS healthkart_price_inr NUMERIC(10,2);
ALTER TABLE variants ADD COLUMN IF NOT EXISTS amazon_price_inr NUMERIC(10,2);
ALTER TABLE variants ADD COLUMN IF NOT EXISTS flipkart_price_inr NUMERIC(10,2);

CREATE TABLE IF NOT EXISTS price_listings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_url TEXT,
    price_inr NUMERIC(10,2) NOT NULL,
    in_stock BOOLEAN DEFAULT true,
    scraped_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(variant_id, source)
);

CREATE INDEX IF NOT EXISTS idx_price_listings_variant ON price_listings(variant_id);
CREATE INDEX IF NOT EXISTS idx_price_listings_source ON price_listings(source);
        `);
    } else if (!error) {
        console.log('\n[OK] price_listings table is ready!');
    } else {
        console.log('\nError:', error);
    }
}

migrate();
