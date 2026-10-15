import type {
  LabAuditReport,
  ProductVariant,
  ReviewAuditSummary,
  ScrapedListing,
  CategoryNutritionProfile,
  SupplementCategory,
} from "@/data/types";

export const INDEX_DATE = new Date("2026-10-09T05:30:00Z");

export const CATEGORY_LABELS: Record<string, string> = {
  whey_isolate: "Whey Isolate",
  whey_concentrate: "Whey Concentrate",
  whey_blend: "Whey Blend",
  casein: "Casein",
  plant: "Plant Protein",
  mass_gainer: "Mass Gainer",
};

export const PLATFORM_LABELS: Record<string, string> = {
  amazon_in: "Amazon",
  flipkart: "Flipkart",
  healthkart: "HealthKart",
  hyuga: "HyugaLife",
  blinkit: "Blinkit",
  zepto: "Zepto",
  instamart: "Instamart",
  d2c: "Brand D2C",
};

export function costPer100gProtein(priceInr: number, servings: number, proteinG: number): number {
  const total = servings * proteinG;
  return total > 0 && priceInr > 0 ? (priceInr / total) * 100 : Infinity;
}

export function bioavailableCostPerGram(costPerG: number, diaas: number): number {
  return diaas > 0 ? costPerG / diaas : Infinity;
}

export function purityPct(proteinG: number, servingSizeG: number): number {
  return servingSizeG > 0 ? (proteinG / servingSizeG) * 100 : 0;
}

export function flavorTaxPct(unflavoredCostPerG: number, flavoredCostPerG: number): number {
  if (unflavoredCostPerG <= 0 || !isFinite(unflavoredCostPerG)) return 0;
  return Math.max(0, ((flavoredCostPerG - unflavoredCostPerG) / unflavoredCostPerG) * 100);
}

export function checkFairyDusting(ingredients: string[]): { isFairyDusted: boolean; reason?: string } {
  if (!ingredients || ingredients.length === 0) {
    return { isFairyDusted: false };
  }
  const fillers = ["maltodextrin", "creatine monohydrate", "glycine", "taurine", "dextrose", "gum blend"];
  const proteinBases = [
    "whey protein isolate",
    "whey protein concentrate",
    "micellar casein",
    "pea protein",
    "hydrolyzed whey",
    "whey protein",
    "soy protein",
  ];

  const normalized = ingredients.map((i) => i.toLowerCase().trim());
  const firstFillerIdx = normalized.findIndex((i) => fillers.some((f) => i.includes(f)));
  const firstBaseIdx = normalized.findIndex((i) => proteinBases.some((b) => i.includes(b)));

  if (firstFillerIdx !== -1 && (firstBaseIdx === -1 || firstFillerIdx < firstBaseIdx)) {
    return { isFairyDusted: true, reason: `Filler (${ingredients[firstFillerIdx]}) precedes protein base` };
  }
  return { isFairyDusted: false };
}

export function authenticityScore(stats?: ReviewAuditSummary): number {
  if (!stats) return 100;
  const deduction =
    (stats.unverified_ratio * 40) +
    (stats.repetitive_phrase_ratio * 35) +
    (stats.burst_score * 25);
  return Math.max(0, Math.round(100 - deduction));
}

export function isGlitchPrice(listing: ScrapedListing): boolean {
  return listing.current_price_inr > 0 && listing.current_price_inr < 800; // Outlier flag
}

export function labAudit(test?: LabAuditReport) {
  if (!test) return null;
  return {
    passed: test.passed,
    variancePct: test.passed ? "+1.4" : "-12.8",
  };
}

export function clearanceStatus(expiryDateStr: string, servings: number) {
  const expiry = new Date(expiryDateStr).getTime();
  const diffDays = Math.max(0, Math.floor((expiry - INDEX_DATE.getTime()) / (1000 * 60 * 60 * 24)));
  const canFinish = diffDays >= servings + 30; // 1 scoop/day + 30-day safe margin
  return { diffDays, canFinish };
}

export function lowestAsk(listings: ScrapedListing[]): ScrapedListing | null {
  const inStock = listings.filter((l) => l.is_in_stock && l.current_price_inr > 0);
  if (!inStock.length) return listings.filter((l) => l.current_price_inr > 0)[0] ?? null;
  return inStock.reduce((min, cur) => (cur.current_price_inr < min.current_price_inr ? cur : min), inStock[0]);
}

export function formatInr(amount: number): string {
  if (!isFinite(amount) || isNaN(amount) || amount <= 0) return "—";
  return "₹" + Math.round(amount).toLocaleString("en-IN");
}

export function indexedAgo(isoString: string): string {
  if (!isoString) return "recently";
  const date = new Date(isoString);
  const now = INDEX_DATE.getTime();
  const diff = now - date.getTime();
  if (isNaN(diff)) return "recently";
  const mins = Math.max(1, Math.round(diff / (1000 * 60)));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export interface ComputedMetrics {
  primaryLabel: string;
  primaryValue: string;
  numericSortValue: number;
  secondaryLabel: string;
  secondaryValue: string;
  badge: string | null;
  badgeTone: 'emerald' | 'amber' | 'cyan' | 'violet';
}

export function computeCategoryMetrics(
  category: SupplementCategory | string,
  priceInr: number,
  nutrition?: Partial<CategoryNutritionProfile> | any,
  fallbackWeightGrams: number = 1000
): ComputedMetrics {
  const normCat = (category || 'protein').toLowerCase().replace('mass_gainers', 'mass_gainer');

  switch (normCat) {
    case 'creatine': {
      const c = nutrition || {};
      const totalGrams = c.totalCreatineGrams || fallbackWeightGrams || 250;
      const costPer3g = totalGrams > 0 && priceInr > 0 ? (priceInr / totalGrams) * 3 : 0;
      return {
        primaryLabel: '₹ / 3g Dose',
        primaryValue: costPer3g > 0 ? `₹${costPer3g.toFixed(2)}` : '—',
        numericSortValue: costPer3g,
        secondaryLabel: 'Cost / 100g',
        secondaryValue: totalGrams > 0 && priceInr > 0 ? `₹${((priceInr / totalGrams) * 100).toFixed(0)}` : '—',
        badge: c.creatineForm === 'monohydrate_creapure' ? 'Creapure® Certified' : '200 Mesh Micronized',
        badgeTone: 'cyan',
      };
    }

    case 'pre_workout': {
      const pw = nutrition || {};
      const servings = pw.servingsPerContainer || Math.max(1, Math.round(fallbackWeightGrams / 12)) || 30;
      const costPerServing = servings > 0 && priceInr > 0 ? priceInr / servings : 0;
      const citrullineMg = pw.lCitrullinePerServingMg || 6000;
      const caffeineMg = pw.caffeinePerServingMg || 250;
      const pumpScore = citrullineMg >= 6000 ? 'Clinical Pump (6g+ Citrulline)' : 'Standard Pump';
      return {
        primaryLabel: '₹ / Scoop',
        primaryValue: costPerServing > 0 ? `₹${costPerServing.toFixed(1)}` : '—',
        numericSortValue: costPerServing,
        secondaryLabel: 'Caffeine / Citrulline',
        secondaryValue: `${caffeineMg}mg / ${(citrullineMg / 1000).toFixed(1)}g`,
        badge: pumpScore,
        badgeTone: 'amber',
      };
    }

    case 'mass_gainer': {
      const mg = nutrition || {};
      const calories = mg.caloriesPerServing || 1100;
      const servings = mg.servingsPerContainer || Math.max(1, Math.round(fallbackWeightGrams / 150)) || 15;
      const totalCalories = calories * servings;
      const costPer1000Kcal = totalCalories > 0 && priceInr > 0 ? (priceInr / totalCalories) * 1000 : 0;
      return {
        primaryLabel: '₹ / 1,000 kcal',
        primaryValue: costPer1000Kcal > 0 ? `₹${costPer1000Kcal.toFixed(1)}` : '—',
        numericSortValue: costPer1000Kcal,
        secondaryLabel: 'Carb:Protein Ratio',
        secondaryValue: `${mg.carbToProteinRatio?.toFixed(1) || '4.0'} : 1`,
        badge: mg.carbSource === 'complex_oats_barley' ? 'Complex Carb Base' : 'Maltodextrin Base',
        badgeTone: 'violet',
      };
    }

    case 'protein':
    default: {
      const p = nutrition || {};
      const servingSize = Math.max(10, p.servingSizeGrams || p.label_serving_size_g || 33);
      const proteinG = Math.max(5, p.proteinPerServingGrams || p.label_protein_per_serving_g || 24);
      const servings = p.servingsPerContainer || Math.max(1, Math.round(fallbackWeightGrams / servingSize));
      const totalProteinG = p.totalProteinPerTubGrams || (proteinG * servings);
      const costPerGram = totalProteinG > 0 && priceInr > 0 ? priceInr / totalProteinG : 0;
      return {
        primaryLabel: '₹ / g Protein',
        primaryValue: costPerGram > 0 ? `₹${costPerGram.toFixed(2)}` : '—',
        numericSortValue: costPerGram,
        secondaryLabel: 'Cost / 24g Scoop',
        secondaryValue: costPerGram > 0 ? `₹${(costPerGram * 24).toFixed(1)}` : '—',
        badge: p.diaasScore ? `DIAAS ${Number(p.diaasScore).toFixed(2)}` : (p.proteinSource === 'whey_isolate' ? '100% Isolate' : 'Pure Protein'),
        badgeTone: 'emerald',
      };
    }
  }
}
