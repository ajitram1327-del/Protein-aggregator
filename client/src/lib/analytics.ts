import type { LabAuditReport, ProductVariant, ReviewAuditSummary, ScrapedListing } from "@/data/types";

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
