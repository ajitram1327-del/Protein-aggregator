# UI Development Handoff

## Current Project State (Backend & Database)
- **Database (Supabase):** Contains the Sneakopedia-style highly normalized catalog (`products`, `variants`, `price_listings`).
- **Scraper Engine:** The `catalog_builder.py` pipeline (Phase 1.5) was paused. However, we have successfully extracted and cleaned **over 2,300 perfect products**. This is more than enough live data to begin building and testing the UI.
- **Frontend Framework:** Next.js App Router (located in `web/` or currently `client/`).

## Task for the New Session
The user wants to start building the **Next.js Web Dashboard** (the "Sneakopedia" for supplements). 

### UI Requirements
1. **Catalog Search:** Users should be able to search the master `products` table (e.g., "Optimum Nutrition Gold Standard").
2. **Product Page:** Display the `base_name` and `brand`.
3. **Selectors:** Users should be able to select a specific `flavor` and `weight_grams` from the `variants` table.
4. **Price Comparison:** Once a variant is selected, display the prices and URLs from the `price_listings` table (comparing Amazon, HealthKart, etc.).

### Immediate Next Steps for the Agent
1. Inspect the Supabase schema using the provided Supabase URL and Key in `.env`.
2. Initialize or repair the Next.js `client/` folder.
3. Build the backend API calls (or Supabase client calls) to fetch the 2,300 products we already have.
4. Scaffold the main dashboard layout.
