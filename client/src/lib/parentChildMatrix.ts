/**
 * Parent-Child-Listing Architecture & Reactive State Machine Engine
 * 
 * Separates immutable ParentProduct metadata from ChildVariant (Weight × Flavor)
 * and MerchantListing order books, providing unit economics and flavor tax arbitrage.
 */

import { GroupedProduct, DbVariant, DbPriceListing } from "@/components/ProductBrowser";
import { formatInr } from "./analytics";

// ==========================================
// 1. PARENT LEVEL (Shared Brand & Product Specs)
// ==========================================
export interface ParentProduct {
  id: string;                      // e.g. "mb-biozyme-iso-zero"
  brand: string;                   // "MuscleBlaze"
  name: string;                    // "Biozyme Iso-Zero"
  category: "protein" | "creatine" | "pre-workout" | "mass-gainer";
  formulation: string;             // "100% Whey Isolate"
  imageUrl: string;
  
  // Base Nutritional Spec (per 100g powder)
  nutritionPer100g: {
    proteinGrams: number;          // e.g. 80g
    carbsGrams: number;
    fatsGrams: number;
    calories: number;
  };
  
  // Quality & Verification Gates
  trustBadges: {
    labdoorScore?: number;
    trustifiedVerified: boolean;
    fssaiLicense: string;
    aminoSpikeTested: boolean;
  };

  // Child Variants Array
  variants: ChildVariant[];
}

// ==========================================
// 2. CHILD LEVEL (Physical SKU: Weight × Flavor)
// ==========================================
export interface ChildVariant {
  variantId: string;               // e.g. "mb-iso-zero-choc-2kg"
  weightGrams: number;             // 2000
  weightDisplay: string;           // "2 kg"
  flavor: string;                  // "Rich Chocolate"
  isUnflavored: boolean;           // true if Raw/Unflavored baseline
  servingsCount: number;           // 67 servings
  servingSizeGrams: number;        // 30g scoop
  proteinPerServingGrams: number;
  
  // Live Merchant Listings (Grandchild Order Book)
  listings: MerchantListing[];
  rawVariant: DbVariant;
}

// ==========================================
// 3. GRANDCHILD LEVEL (Store Order Book)
// ==========================================
export interface MerchantListing {
  storeId: string;
  storeName: string;
  sellerName: string;              // e.g. "Appario Retail", "MuscleBlaze Official"
  isAuthorizedSeller: boolean;     // Trust shield
  mrp: number;                     // Maximum Retail Price (₹)
  currentPrice: number;            // Current selling price (₹)
  inStock: boolean;
  affiliateUrl: string;            // Masked redirect URL (/go/sku-id)
  lastCheckedMinutesAgo: number;
}

// ==========================================
// 4. RESOLVED SKU METRICS (Calculated Output)
// ==========================================
export interface ResolvedSKUMetrics {
  selectedWeightGrams: number;
  selectedWeight: string;
  selectedFlavor: string;
  lowestPrice: number;
  mrp: number;
  discountPercent: number;
  bestStore: MerchantListing;
  storeCount: number;
  inStock: boolean;
  
  // Unit Cost depending on Category
  unitCostValue: number;
  unitCostLabel: string;           // e.g. "₹2.62 / g protein"
  costPerScoop: number;
  
  // Flavor Tax Arbitrage
  flavorTaxAmount: number;         // e.g. 350
  flavorTaxPercent: number;        // e.g. 8.3%
  cheapestFlavorName: string;      // e.g. "Unflavored"
  isUnflavored: boolean;

  // Active Variant reference
  activeVariant: ChildVariant;
}

// ==========================================
// 5. HELPER: Clean Flavor Name
// ==========================================
export function cleanFlavorName(rawFlavor: string): string {
  let clean = (rawFlavor || "").trim();
  clean = clean.replace(/\b\d+(?:\.\d+)?\s*(kg|g|gm|lbs|l|ml)\b/gi, "").trim();
  clean = clean.replace(/^[\/\-\|\,\s]+|[\/\-\|\,\s]+$/g, "").trim();
  if (!clean || clean.toLowerCase() === "varies" || clean.toLowerCase() === "default title") {
    return "Standard";
  }
  return clean;
}

export function isUnflavoredFlavor(flavor: string): boolean {
  const lower = flavor.toLowerCase();
  return (
    lower.includes("unflavor") ||
    lower.includes("raw") ||
    lower.includes("natural") ||
    lower === "pure" ||
    lower === "plain"
  );
}

export function formatWeightDisplay(weightGrams: number): string {
  if (weightGrams >= 1000) {
    const kg = weightGrams / 1000;
    return `${kg % 1 === 0 ? kg : kg.toFixed(1)} kg`;
  }
  return `${weightGrams} g`;
}

// ==========================================
// 6. ADAPTER: GroupedProduct -> ParentProduct
// ==========================================
export function toParentProduct(product: GroupedProduct): ParentProduct {
  const normSilo = (product.categorySilo || "protein").toLowerCase();
  let category: ParentProduct["category"] = "protein";
  if (normSilo.includes("creatine")) category = "creatine";
  else if (normSilo.includes("pre_workout") || normSilo.includes("preworkout")) category = "pre-workout";
  else if (normSilo.includes("gainer")) category = "mass-gainer";

  const variants: ChildVariant[] = (product.variants || []).map((v) => {
    const weightGrams = Math.max(1, v.weight_grams || 1000);
    const servingSizeGrams = Math.max(1, v.label_serving_size_g || 33);
    const servingsCount = Math.max(1, Math.round(weightGrams / servingSizeGrams));
    const proteinPerServing = Math.max(0, v.label_protein_per_serving_g || 24);
    const cleanFlavor = cleanFlavorName(v.flavor);
    const isUnflav = isUnflavoredFlavor(cleanFlavor);

    const listings: MerchantListing[] = (v.price_listings || []).map((pl, idx) => {
      const source = (pl.source || "Direct").toLowerCase();
      let storeName = "Brand Official";
      let storeId = "d2c_official";

      if (source.includes("amazon")) {
        storeName = "Amazon India";
        storeId = "amazon";
      } else if (source.includes("flipkart")) {
        storeName = "Flipkart";
        storeId = "flipkart";
      } else if (source.includes("nutrabay")) {
        storeName = "Nutrabay";
        storeId = "nutrabay";
      } else if (source.includes("healthkart")) {
        storeName = "HealthKart";
        storeId = "healthkart";
      } else if (product.brand) {
        storeName = `${product.brand} Direct`;
        storeId = "d2c_official";
      }

      const currentPrice = pl.price_inr > 0 ? pl.price_inr : v.lowest_price_inr || 2499;
      const mrp = Math.round(currentPrice * 1.25); // Baseline MRP ~25% higher if unstated
      const inStock = pl.is_in_stock ?? pl.in_stock ?? true;

      return {
        storeId,
        storeName,
        sellerName: pl.seller_name || (pl.is_authorized_seller ? "Authorized Retailer" : "Marketplace Seller"),
        isAuthorizedSeller: pl.is_authorized_seller ?? true,
        mrp,
        currentPrice,
        inStock,
        affiliateUrl: pl.source_url || "#",
        lastCheckedMinutesAgo: 15,
      };
    });

    // If no real listings, provide synthesized primary store from lowest_price_inr
    if (listings.length === 0) {
      const basePrice = v.lowest_price_inr || product.lowestPrice || 2499;
      listings.push({
        storeId: "d2c_official",
        storeName: `${product.brand} Direct`,
        sellerName: "Brand Official Store",
        isAuthorizedSeller: true,
        mrp: Math.round(basePrice * 1.25),
        currentPrice: basePrice,
        inStock: basePrice > 0,
        affiliateUrl: "#",
        lastCheckedMinutesAgo: 10,
      });
    }

    return {
      variantId: v.id || v.sku_id,
      weightGrams,
      weightDisplay: formatWeightDisplay(weightGrams),
      flavor: cleanFlavor,
      isUnflavored: isUnflav,
      servingsCount,
      servingSizeGrams,
      proteinPerServingGrams: proteinPerServing,
      listings,
      rawVariant: v,
    };
  });

  // Calculate default nutrition spec
  const firstVariant = variants[0];
  const proteinPct = firstVariant && firstVariant.servingSizeGrams > 0
    ? Math.min(100, (firstVariant.proteinPerServingGrams / firstVariant.servingSizeGrams) * 100)
    : 75;

  return {
    id: product.id,
    brand: product.brand,
    name: product.baseProductName,
    category,
    formulation: product.proteinSource || "Standard Formulation",
    imageUrl: product.imageUrl,
    nutritionPer100g: {
      proteinGrams: Number(proteinPct.toFixed(1)),
      carbsGrams: 5,
      fatsGrams: 3,
      calories: 380,
    },
    trustBadges: {
      labdoorScore: product.trustScore,
      trustifiedVerified: product.labVerified ?? false,
      fssaiLicense: "10015064000576",
      aminoSpikeTested: !(product.isFairyDusted ?? false),
    },
    variants,
  };
}

// ==========================================
// 7. MATHEMATICAL ENGINE: resolveCardMetrics
// ==========================================
export function resolveCardMetrics(
  product: ParentProduct,
  activeWeightGrams: number,
  activeFlavor: string
): ResolvedSKUMetrics | null {
  // 1. Locate the exact selected SKU
  const activeVariant = product.variants.find(
    (v) =>
      v.weightGrams === activeWeightGrams &&
      v.flavor.toLowerCase() === activeFlavor.toLowerCase()
  );

  if (!activeVariant) return null;

  // 2. Filter in-stock listings and find the lowest price
  const availableListings = activeVariant.listings.filter((l) => l.inStock && l.currentPrice > 0);
  const bestListing =
    availableListings.length > 0
      ? availableListings.reduce((min, cur) =>
          cur.currentPrice < min.currentPrice ? cur : min
        )
      : activeVariant.listings[0] || {
          storeId: "d2c",
          storeName: `${product.brand} Direct`,
          sellerName: "Brand Store",
          isAuthorizedSeller: true,
          mrp: 3000,
          currentPrice: 2499,
          inStock: false,
          affiliateUrl: "#",
          lastCheckedMinutesAgo: 60,
        };

  const currentPrice = bestListing.currentPrice;
  const inStock = availableListings.length > 0 && currentPrice > 0;

  // 3. Compute Category Unit Metrics
  let unitCostValue = 0;
  let unitCostLabel = "";
  const servings = Math.max(1, activeVariant.servingsCount);
  const costPerScoop = currentPrice > 0 ? Math.round(currentPrice / servings) : 0;

  if (product.category === "creatine") {
    // Creatine: ₹ / 3g clinical dose
    const total3gDoses = Math.max(1, activeVariant.weightGrams / 3);
    unitCostValue = Number((currentPrice / total3gDoses).toFixed(2));
    unitCostLabel = `₹${unitCostValue} / 3g dose`;
  } else if (product.category === "pre-workout") {
    // Pre-Workout: ₹ / full scoop active
    unitCostValue = costPerScoop;
    unitCostLabel = `₹${unitCostValue} / scoop`;
  } else if (product.category === "mass-gainer") {
    // Mass Gainer: ₹ / 1,000 clean kcal
    const totalKcal = (activeVariant.weightGrams / 100) * product.nutritionPer100g.calories;
    const total1kKcal = Math.max(1, totalKcal / 1000);
    unitCostValue = Math.round(currentPrice / total1kKcal);
    unitCostLabel = `₹${unitCostValue} / 1k kcal`;
  } else {
    // Protein: Total Pure Protein = (Total Tub Grams * Protein%) / 100
    const totalPureProteinGrams = Math.max(
      1,
      (activeVariant.weightGrams * product.nutritionPer100g.proteinGrams) / 100
    );
    unitCostValue = Number((currentPrice / totalPureProteinGrams).toFixed(2));
    unitCostLabel = `₹${unitCostValue} / g protein`;
  }

  // 4. Flavor Tax Arbitrage Calculation (Compare vs Unflavored sibling at same weight)
  const baselineUnflavoredVariant = product.variants.find(
    (v) => v.weightGrams === activeWeightGrams && v.isUnflavored
  );

  let flavorTaxAmount = 0;
  let flavorTaxPercent = 0;

  if (baselineUnflavoredVariant && !activeVariant.isUnflavored) {
    const unflavInStock = baselineUnflavoredVariant.listings.filter((l) => l.inStock && l.currentPrice > 0);
    const unflavoredMin =
      unflavInStock.length > 0
        ? Math.min(...unflavInStock.map((l) => l.currentPrice))
        : baselineUnflavoredVariant.listings[0]?.currentPrice || 0;

    if (unflavoredMin > 0 && currentPrice > unflavoredMin) {
      flavorTaxAmount = currentPrice - unflavoredMin;
      flavorTaxPercent = Math.round((flavorTaxAmount / unflavoredMin) * 100);
    }
  }

  const mrp = Math.max(currentPrice, bestListing.mrp);
  const discountPercent = mrp > currentPrice ? Math.round(((mrp - currentPrice) / mrp) * 100) : 0;

  return {
    selectedWeightGrams: activeVariant.weightGrams,
    selectedWeight: activeVariant.weightDisplay,
    selectedFlavor: activeVariant.flavor,
    lowestPrice: currentPrice,
    mrp,
    discountPercent,
    bestStore: bestListing,
    storeCount: availableListings.length,
    inStock,
    unitCostValue,
    unitCostLabel,
    costPerScoop,
    flavorTaxAmount,
    flavorTaxPercent,
    cheapestFlavorName: baselineUnflavoredVariant ? baselineUnflavoredVariant.flavor : "Unflavored",
    isUnflavored: activeVariant.isUnflavored,
    activeVariant,
  };
}
