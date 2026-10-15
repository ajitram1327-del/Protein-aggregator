# ProteinDX project rules

ProteinDX compares protein and supplement prices across brands and sellers in India. It shows flavour, size, price per seller, nutrition and price history.

## Stack
- Scraper: Python 3.10+, folder `/scraper`. Libraries: `scrapling` (for stealth, IP rotation, Cloudflare bypass), `supabase` (for DB).
- Database: Supabase Postgres. All schema changes go in `/supabase/migrations` as new SQL files. Never edit an old migration.
- Web: Next.js (App Router) + TypeScript + Tailwind + Recharts, folder `/web`. Server components by default.

## Data model (source of truth)
product -> variants (flavor + weight_grams) -> offers (one row per seller URL) -> price_history (one row per price or stock change).
Nutrition (serving_size_g, protein_per_serving_g, ingredients) lives on the product.

## Rules
1. Inspect before you change. Read the existing files and the live schema first. Never assume column names.
2. Never hardcode keys. Use `.env` (git-ignored) and keep `.env.example` current.
3. Never run destructive SQL (drop, truncate, delete without a where clause) or a full scrape without explicit approval. Dry-run first.
4. Validate every scraped value before saving (price > 0, weight plausible, protein <= serving size). Bad rows go to a review status, not into rankings.
5. Never guess nutrition. If it can't be extracted and validated, set `nutrition_source = 'assumed'` and exclude the product from protein-based rankings.
6. Store the raw source payload for each offer so parsing can be fixed later without re-scraping.
7. Do not log or store personal data. Analytics events must be anonymous (random session id, no name, email, IP or fingerprint).
8. Keep functions small and typed. Add or update a test for every parser and matcher you touch.
9. When finished with a task, summarise what changed, what was tested, and what still needs a human decision.
10. Follow the Anti-AI-Slop field guide (`.agents/rules/anti-ai-slop.md`) for all UI and frontend work — no AI visual tells, template layouts, generic buzzwords, or unconsidered styling.
