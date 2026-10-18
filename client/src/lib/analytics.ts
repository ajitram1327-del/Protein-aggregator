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
  return total > 0 && priceInr > 0 ? Number(((priceInr / total) * 100).toFixed(2)) : Infinity;
}

export function bioavailableCostPerGram(costPerG: number, diaas: number): number {
  return diaas > 0 ? Number((costPerG / diaas).toFixed(2)) : Infinity;
}

export function purityPct(proteinG: number, servingSizeG: number): number {
  return servingSizeG > 0 ? Number(((proteinG / servingSizeG) * 100).toFixed(1)) : 0;
}

export function flavorTaxPct(unflavoredCostPerG: number, flavoredCostPerG: number): number {
  if (unflavoredCostPerG <= 0 || !isFinite(unflavoredCostPerG)) return 0;
  return Number(Math.max(0, ((flavoredCostPerG - unflavoredCostPerG) / unflavoredCostPerG) * 100).toFixed(1));
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

export interface AminoSpikeAudit {
  isSpiked: boolean;
  riskLevel: "CLEAN" | "SUSPECTED_SPIKING" | "CONFIRMED_SPIKED";
  badge: string;
  detectedAgents: string[];
  reason?: string;
  meetsMps: boolean;
  leucineG?: number;
}

export function auditAminoSpiking(
  ingredients: string[] | string,
  leucineG?: number | null,
  proteinG?: number | null
): AminoSpikeAudit {
  const ingList = Array.isArray(ingredients)
    ? ingredients
    : (ingredients || "").split(/[,|\n]/).map((s) => s.trim()).filter(Boolean);

  const spikingAgents = [
    "glycine", "l-glycine",
    "taurine", "l-taurine",
    "creatine", "creatine monohydrate",
    "glutamine", "l-glutamine",
    "alanine", "l-alanine",
    "proline", "l-proline",
    "arginine", "l-arginine",
  ];

  const detected: string[] = [];
  const normalized = ingList.map((i) => i.toLowerCase());

  for (const agent of spikingAgents) {
    if (normalized.some((ing) => ing.includes(agent))) {
      detected.push(agent);
    }
  }

  const effectiveProt = proteinG && proteinG > 0 ? proteinG : 24.0;
  const effectiveLeucine = leucineG && leucineG > 0 ? leucineG : detected.length > 0 ? effectiveProt * 0.065 : effectiveProt * 0.108;
  const meetsMps = effectiveLeucine >= 2.5 && detected.length === 0;

  if (detected.length >= 2) {
    return {
      isSpiked: true,
      riskLevel: "CONFIRMED_SPIKED",
      badge: "⚠️ High Amino Spiking Risk",
      detectedAgents: detected,
      reason: `Added free-form aminos (${detected.join(", ")}) detected inflating nitrogen content`,
      meetsMps: false,
      leucineG: Math.round(effectiveLeucine * 10) / 10,
    };
  }

  if (detected.length === 1) {
    return {
      isSpiked: true,
      riskLevel: "SUSPECTED_SPIKING",
      badge: "⚠️ Added Free-Form Aminos",
      detectedAgents: detected,
      reason: `Added free-form ${detected[0]} detected`,
      meetsMps: false,
      leucineG: Math.round(effectiveLeucine * 10) / 10,
    };
  }

  return {
    isSpiked: false,
    riskLevel: "CLEAN",
    badge: "✓ Clean Amino Profile",
    detectedAgents: [],
    meetsMps,
    leucineG: Math.round(effectiveLeucine * 10) / 10,
  };
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

export function indexedAgo(isoString?: string): string {
  if (!isoString) return "recently";
  const date = new Date(isoString);
  const time = date.getTime();
  if (isNaN(time)) return "recently";
  const now = Date.now();
  const diff = Math.max(0, now - time);
  const mins = Math.max(1, Math.round(diff / (1000 * 60)));
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export interface ComputedMetrics {
  primaryLabel: string;
  primaryValue: string;
  numericSortValue: number;
  secondaryLabel: string;
  secondaryValue: string;
  badge: string | null;
  badgeTone: 'emerald' | 'amber' | 'cyan' | 'violet' | 'slate' | 'rose';
  isPending: boolean;
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
      const totalGrams = Number(c.totalCreatineGrams) || Number(fallbackWeightGrams) || 0;
      const costPer3g = totalGrams > 0 && priceInr > 0 ? (priceInr / totalGrams) * 3 : 0;
      return {
        primaryLabel: '₹ / 3g Dose',
        primaryValue: costPer3g > 0 ? `₹${costPer3g.toFixed(2)}` : '—',
        numericSortValue: costPer3g > 0 ? costPer3g : Infinity,
        secondaryLabel: 'Cost / 100g',
        secondaryValue: totalGrams > 0 && priceInr > 0 ? `₹${((priceInr / totalGrams) * 100).toFixed(0)}` : '—',
        badge: c.creatineForm === 'monohydrate_creapure' ? 'Creapure® Certified' : '200 Mesh Micronized',
        badgeTone: 'cyan',
        isPending: costPer3g <= 0,
      };
    }

    case 'pre_workout': {
      const pw = nutrition || {};
      const servings = Number(pw.servingsPerContainer) || (fallbackWeightGrams > 0 ? Math.max(1, Math.round(fallbackWeightGrams / 12)) : 0);
      const costPerServing = servings > 0 && priceInr > 0 ? priceInr / servings : 0;
      const citrullineMg = Number(pw.lCitrullinePerServingMg) || 0;
      const caffeineMg = Number(pw.caffeinePerServingMg) || 0;
      const pumpScore = citrullineMg >= 6000 ? 'Clinical Pump (6g+ Citrulline)' : citrullineMg > 0 ? 'Standard Pump' : 'Pre-Workout Formula';
      return {
        primaryLabel: '₹ / Scoop',
        primaryValue: costPerServing > 0 ? `₹${costPerServing.toFixed(1)}` : '—',
        numericSortValue: costPerServing > 0 ? costPerServing : Infinity,
        secondaryLabel: 'Caffeine / Citrulline',
        secondaryValue: caffeineMg > 0 || citrullineMg > 0 ? `${caffeineMg}mg / ${(citrullineMg / 1000).toFixed(1)}g` : 'Formula Profile',
        badge: pumpScore,
        badgeTone: 'amber',
        isPending: costPerServing <= 0,
      };
    }

    case 'mass_gainer': {
      const mg = nutrition || {};
      const calories = Number(mg.caloriesPerServing) || 0;
      const servings = Number(mg.servingsPerContainer) || (fallbackWeightGrams > 0 && calories > 0 ? Math.max(1, Math.round(fallbackWeightGrams / 150)) : 0);
      const totalCalories = calories * servings;
      const costPer1000Kcal = totalCalories > 0 && priceInr > 0 ? (priceInr / totalCalories) * 1000 : 0;
      return {
        primaryLabel: '₹ / 1,000 kcal',
        primaryValue: costPer1000Kcal > 0 ? `₹${costPer1000Kcal.toFixed(1)}` : '—',
        numericSortValue: costPer1000Kcal > 0 ? costPer1000Kcal : Infinity,
        secondaryLabel: 'Carb:Protein Ratio',
        secondaryValue: mg.carbToProteinRatio ? `${mg.carbToProteinRatio.toFixed(1)} : 1` : '—',
        badge: mg.carbSource === 'complex_oats_barley' ? 'Complex Carb Base' : 'Calorie Formula',
        badgeTone: 'violet',
        isPending: costPer1000Kcal <= 0,
      };
    }

    case 'snacks': {
      const p = nutrition || {};
      const servingSize = Number(p.servingSizeGrams || p.label_serving_size_g || 0);
      const proteinG = Number(p.proteinPerServingGrams || p.label_protein_per_serving_g || 0);
      const effectiveWeight = fallbackWeightGrams > 0 ? fallbackWeightGrams : (servingSize > 0 ? servingSize : 100);
      const costPer100g = effectiveWeight > 0 && priceInr > 0 ? (priceInr / effectiveWeight) * 100 : 0;

      return {
        primaryLabel: '₹ / 100g',
        primaryValue: costPer100g > 0 ? `₹${costPer100g.toFixed(1)}` : '—',
        numericSortValue: costPer100g > 0 ? costPer100g : Infinity,
        secondaryLabel: proteinG > 0 ? `${proteinG}g Protein/Serving` : 'Serving Profile',
        secondaryValue: proteinG > 0 ? `${proteinG}g Prot` : (servingSize > 0 ? `${servingSize}g Pack` : 'Functional Snack'),
        badge: 'High-Protein Snack',
        badgeTone: 'rose',
        isPending: costPer100g <= 0,
      };
    }

    case 'protein':
    default: {
      const p = nutrition || {};
      const servingSize = Number(p.servingSizeGrams || p.label_serving_size_g || 0);
      const proteinG = Number(p.proteinPerServingGrams || p.label_protein_per_serving_g || 0);

      // Quarantine check: If servingSize or proteinG is missing, zero, or suspicious, do not invent 24g/33g!
      const isNutritionValid = servingSize > 0 && proteinG > 0 && proteinG <= servingSize;
      
      if (!isNutritionValid) {
        return {
          primaryLabel: '₹ / g Protein',
          primaryValue: 'Pending',
          numericSortValue: Infinity,
          secondaryLabel: 'Nutrition Status',
          secondaryValue: 'Pending Verification',
          badge: 'Pending Verification',
          badgeTone: 'slate',
          isPending: true,
        };
      }

      const servings = Number(p.servingsPerContainer) || Math.max(1, Math.round(fallbackWeightGrams / servingSize));
      const totalProteinG = Number(p.totalProteinPerTubGrams) || (proteinG * servings);
      const costPerGram = totalProteinG > 0 && priceInr > 0 ? priceInr / totalProteinG : 0;

      return {
        primaryLabel: '₹ / g Protein',
        primaryValue: costPerGram > 0 ? `₹${costPerGram.toFixed(2)}` : '—',
        numericSortValue: costPerGram > 0 ? costPerGram : Infinity,
        secondaryLabel: `Cost / ${proteinG}g Scoop`,
        secondaryValue: costPerGram > 0 ? `₹${(costPerGram * proteinG).toFixed(1)}` : '—',
        badge: p.diaasScore ? `DIAAS ${Number(p.diaasScore).toFixed(2)}` : (p.proteinSource === 'whey_isolate' ? '100% Isolate' : 'Pure Protein'),
        badgeTone: 'emerald',
        isPending: costPerGram <= 0,
      };
    }
  }
}
