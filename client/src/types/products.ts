export type NutritionQualityState =
  | "verified"
  | "observed"
  | "pending_verification"
  | "stale"
  | "unknown"
  | "not_applicable";

export interface DbPriceListing {
  source: string;
  price_inr: number;
  source_url: string;
  seller_name?: string;
  is_authorized_seller?: boolean;
  is_in_stock?: boolean;
  in_stock?: boolean;
  scraped_at?: string;
}

export interface DbVariant {
  id: string;
  sku_id: string;
  flavor: string;
  weight_grams: number;
  lowest_price_inr: number;
  best_value_metric: number | null;
  label_serving_size_g?: number | null;
  label_protein_per_serving_g?: number | null;
  calculated_purity_pct?: number | null;
  nutrition_status?: NutritionQualityState;
  raw_json_data: any;
  price_listings: DbPriceListing[];
  has_bot_reviews?: boolean;
  authenticity_score?: number;
  last_observed_at?: string;
  seller_count?: number;
}

export interface GroupedProduct {
  id: string;
  brand: string;
  baseProductName: string;
  categorySilo: string;
  proteinSource: string;
  imageUrl: string;
  variants: DbVariant[];
  lowestPrice: number;
  bestValueMetric: number | null;
  nutritionStatus?: NutritionQualityState;
  lastObservedAt?: string;
  sellerCount?: number;
  isFairyDusted?: boolean;
  aminoSpikeRisk?: boolean;
  aminoSpikeBadge?: string;
  labVerified?: boolean;
  trustScore?: number;
  labReportUrl?: string;
}

export const CANONICAL_CATEGORIES = [
  {
    id: "protein",
    siloAliases: [
      "protein",
      "whey",
      "plant",
      "whey_protein",
      "whey_&_plant_protein",
      "whey & plant protein"
    ],
    title: "Whey & Plant Protein",
    shortLabel: "Protein",
    tagline: "Benchmark by ₹ / g Pure Protein",
    description: "Stop paying for filler and maltodextrin. Compare authentic Isolate, Concentrate, and Plant blends with verified DIAAS scores.",
    metricExample: "Lowest ask: ₹1.62 / g Protein",
    color: "border-emerald-500/40 hover:border-emerald-500 bg-emerald-950/5",
    activePill: "border-emerald-500 text-emerald-800 bg-emerald-50",
    badge: "Whey & Isolate",
    badgeTone: "bg-emerald-50 text-emerald-700 border-emerald-200",
    primaryHeader: "₹ / g Protein",
    secondaryHeader: "Cost / Scoop",
    metaTitle: "Whey & Plant Protein Intelligence",
    metaSubtitle: "Benchmark by ₹ / g pure protein, DIAAS digestibility scores, and flavor tax.",
  },
  {
    id: "creatine",
    siloAliases: [
      "creatine",
      "creatine_monohydrate",
      "creatine monohydrate"
    ],
    title: "Creatine Monohydrate",
    shortLabel: "Creatine",
    tagline: "Benchmark by ₹ / 3g Verified Dose",
    description: "Creapure® seals, 200-mesh micronized purity tests, and direct price comparisons on raw unflavored powder across authorized sellers.",
    metricExample: "Lowest ask: ₹4.20 / 3g Serving",
    color: "border-cyan-500/40 hover:border-cyan-500 bg-cyan-950/5",
    activePill: "border-cyan-500 text-cyan-800 bg-cyan-50",
    badge: "Creapure & 200 Mesh",
    badgeTone: "bg-cyan-50 text-cyan-800 border-cyan-200",
    primaryHeader: "₹ / 3g Dose",
    secondaryHeader: "Cost / 100g",
    metaTitle: "Creatine Monohydrate Purity Screener",
    metaSubtitle: "Only showing verified creatine products. Benchmark by ₹ / 3g verified dose and Creapure® certification.",
  },
  {
    id: "pre_workout",
    siloAliases: [
      "pre_workout",
      "preworkout",
      "pre-workout",
      "pre-workout_&_pump",
      "pre-workout & pump"
    ],
    title: "Pre-Workout & Pump",
    shortLabel: "Pre-Workout",
    tagline: "Benchmark by Cost per Clinical Scoop",
    description: "Expose underdosed proprietary blends. We calculate true value based on active L-Citrulline, Beta-Alanine, and Caffeine dosages.",
    metricExample: "Lowest ask: ₹32 / Clinical Scoop",
    color: "border-amber-500/40 hover:border-amber-500 bg-amber-950/5",
    activePill: "border-amber-500 text-amber-800 bg-amber-50",
    badge: "Open Label Dosages",
    badgeTone: "bg-amber-50 text-amber-800 border-amber-200",
    primaryHeader: "₹ / Scoop",
    secondaryHeader: "Caffeine / Citrulline",
    metaTitle: "Pre-Workout Active Dosage Screener",
    metaSubtitle: "Expose underdosed proprietary blends. Normalized by clinical L-Citrulline, Beta-Alanine, and Caffeine dosages.",
  },
  {
    id: "mass_gainer",
    siloAliases: [
      "mass_gainer",
      "mass_gainers",
      "gainer",
      "gainers",
      "mass gainers"
    ],
    title: "Mass Gainers",
    shortLabel: "Mass Gainer",
    tagline: "Benchmark by ₹ / 1,000 kcal & Carb Ratio",
    description: "Identify clean whole-food oat/barley formulas vs. cheap 80% sugar/maltodextrin tubs. Track true calorie-to-protein ratios.",
    metricExample: "Lowest ask: ₹74 / 1,000 kcal",
    color: "border-violet-500/40 hover:border-violet-500 bg-violet-950/5",
    activePill: "border-violet-500 text-violet-800 bg-violet-50",
    badge: "Calorie Arbitrage",
    badgeTone: "bg-violet-50 text-violet-800 border-violet-200",
    primaryHeader: "₹ / 1,000 kcal",
    secondaryHeader: "Carb:Protein Ratio",
    metaTitle: "Mass Gainer Calorie Arbitrage",
    metaSubtitle: "Identify clean whole-food oat/barley formulas vs cheap 80% sugar/maltodextrin tubs.",
  },
  {
    id: "snacks",
    siloAliases: [
      "snacks",
      "snack",
      "protein_snacks",
      "protein_snacks_&_bars",
      "protein snacks & bars"
    ],
    title: "Protein Snacks & Bars",
    shortLabel: "Snacks",
    tagline: "Benchmark by ₹ / 100g & Protein Density",
    description: "Protein wafers, bars, cookies, and functional snacks ranked by true protein-to-calorie ratio and cost per 100g.",
    metricExample: "Lowest ask: ₹69 / 100g",
    color: "border-rose-500/40 hover:border-rose-500 bg-rose-950/5",
    activePill: "border-rose-500 text-rose-800 bg-rose-50",
    badge: "Functional Snacks",
    badgeTone: "bg-rose-50 text-rose-800 border-rose-200",
    primaryHeader: "₹ / 100g",
    secondaryHeader: "Protein / Serving",
    metaTitle: "Protein Snacks & Bars Value Screener",
    metaSubtitle: "Benchmark protein wafers, bars, cookies, and functional snacks by cost per 100g and protein density.",
  },
];
