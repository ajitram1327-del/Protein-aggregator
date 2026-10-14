import type { ProductBundle, ProductVariant, ScrapedListing } from "@/data/types";
import {
  authenticityScore,
  checkFairyDusting,
  costPer100gProtein,
  flavorTaxPct,
  lowestAsk,
  purityPct,
} from "./analytics";

export interface VariantRow {
  variant: ProductVariant;
  offers: ScrapedListing[];
  best: ScrapedListing | null;
  costPer100g: number;
  bioPerG: number;
  purity: number;
}

export interface FlavorGroup {
  flavor: string;
  rows: VariantRow[];
  best: VariantRow | null;
  flavorTax: number;
}

export interface ScreenerRow {
  bundle: ProductBundle;
  best: VariantRow | null;
  costPer100g: number;
  purity: number;
  flavorTax: number;
  inStock: boolean;
  labPassed: boolean | null;
  fairyDusted: boolean;
  authenticity: number;
  groups: FlavorGroup[];
}

export function variantRows(bundle: ProductBundle): VariantRow[] {
  return bundle.variants.map((v) => {
    const offers = bundle.listings.filter((l) => l.variant_id === v.id);
    const best = lowestAsk(offers);
    const costPer100g = best
      ? costPer100gProtein(best.current_price_inr, v.label_total_servings, v.label_protein_per_serving_g)
      : Infinity;
    const purity = purityPct(v.label_protein_per_serving_g, v.label_serving_size_g);
    const diaas = bundle.product.baseline_diaas_score > 0 ? bundle.product.baseline_diaas_score : 1.0;
    const bioPerG = isFinite(costPer100g) ? costPer100g / (100 * diaas) : Infinity;

    return { variant: v, offers, best, costPer100g, bioPerG, purity };
  });
}

export function flavorGroups(bundle: ProductBundle): FlavorGroup[] {
  const vRows = variantRows(bundle);
  const byFlavor = new Map<string, VariantRow[]>();

  vRows.forEach((r) => {
    const list = byFlavor.get(r.variant.flavor_name) ?? [];
    list.push(r);
    byFlavor.set(r.variant.flavor_name, list);
  });

  const unflavored = vRows.find((r) => r.variant.is_unflavored);
  const unflavoredCost = unflavored && isFinite(unflavored.costPer100g) ? unflavored.costPer100g : 0;

  return Array.from(byFlavor.entries()).map(([flavor, rows]) => {
    const best = rows.reduce<VariantRow | null>(
      (min, cur) => (!min || cur.costPer100g < min.costPer100g ? cur : min),
      null
    );
    const flavorTax =
      unflavoredCost > 0 && best && isFinite(best.costPer100g)
        ? flavorTaxPct(unflavoredCost, best.costPer100g)
        : 0;
    return { flavor, rows, best, flavorTax };
  });
}

export function screenerRow(bundle: ProductBundle): ScreenerRow {
  const groups = flavorGroups(bundle);
  const allRows = groups.flatMap((g) => g.rows);
  const best = allRows.reduce<VariantRow | null>(
    (min, cur) => (!min || cur.costPer100g < min.costPer100g ? cur : min),
    null
  );

  const inStock = allRows.some((r) => r.best?.is_in_stock);
  const unflavored = allRows.find((r) => r.variant.is_unflavored);
  const flavorTax =
    unflavored && best && isFinite(unflavored.costPer100g) && isFinite(best.costPer100g)
      ? flavorTaxPct(unflavored.costPer100g, best.costPer100g)
      : 0;
  const labPassed = bundle.labTest ? bundle.labTest.passed : null;
  const fairyDusted = checkFairyDusting(bundle.product.ingredients).isFairyDusted;
  const authenticity = authenticityScore(bundle.reviewStats);

  return {
    bundle,
    best,
    costPer100g: best?.costPer100g ?? Infinity,
    purity: best?.purity ?? 0,
    flavorTax,
    inStock,
    labPassed,
    fairyDusted,
    authenticity,
    groups,
  };
}
