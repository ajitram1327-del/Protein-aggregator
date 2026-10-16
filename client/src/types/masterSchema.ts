/**
 * Master Universal JSON Schema Contract (Proteindex PRD v2.1 Section 2)
 * Uniform data contract consumed across RESTful APIs and frontend screeners.
 */

export interface PackagingInfo {
  weightGrams: number;
  servingsCount: number;
  servingSizeGrams: number;
}

export type NutritionStatus =
  | "verified"
  | "observed"
  | "pending_verification"
  | "stale"
  | "unknown"
  | "not_applicable";

export interface NutritionalProfile {
  activeIngredientPerServingGrams: number | null;
  pdcaasScore?: number | null;
  bioavailableProteinPerServing: number | null;
  proteinPurityPct: number | null;
  caloriesPerServing: number | null;
  carbsPerServingGrams: number | null;
  nutritionStatus: NutritionStatus;
  nutritionStatusReason?: string;
  diaasScore?: number | null;
  diaasBasis?: string | null;
  diaasSourceEvidence?: any;
  aminoAcidCompletenessStatus?: string | null;
}

export interface UsefulDoseAnalysis {
  leucinePerServingGrams: number | null;
  meetsMpsThreshold: boolean | null;
  aminoSpikeRisk: boolean;
  fillersDetected: string[];
}

export interface EqualizerMetrics {
  primaryMetricLabel: string;
  primaryMetricValue: number | null;
  secondaryMetricLabel: string;
  secondaryMetricValue: number | null;
  isReliable: boolean;
}

export interface VendorOffer {
  platform: string;
  url: string;
  priceInr: number;
  inStock?: boolean;
  sellerName?: string;
  isAuthorizedSeller?: boolean;
  observedAt?: string;
}

export interface PricingSummary {
  lowestPriceInr: number;
  lowestAuthorizedPriceInr?: number;
  sellerCount: number;
  lastObservedAt?: string;
  inStock: boolean;
  vendorOffers: VendorOffer[];
}

export interface FSSAIInfo {
  licenseNumber?: string;
  status: string;
  verifiedManufacturer?: string;
}

export interface VerificationRecord {
  authority: string;
  labName: string;
  status: "PASS" | "FAIL";
  proofUrl?: string;
}

export interface VerificationInfo {
  tier: "gold" | "silver" | "bronze";
  fssai: FSSAIInfo;
  records: VerificationRecord[];
}

export interface MasterUniversalSKU {
  skuId: string;
  brand: string;
  productName: string;
  categorySilo: string;
  subCategory: string;
  flavor: string;
  imageUrl?: string;
  packaging: PackagingInfo;
  nutritionalProfile: NutritionalProfile;
  usefulDoseAnalysis: UsefulDoseAnalysis;
  equalizerMetrics: EqualizerMetrics;
  pricing: PricingSummary;
  verification: VerificationInfo;
}

/**
 * Shared Domain Screener View Model (PRD Section 8.1)
 */
export interface ProductListingView {
  productId: string;
  variantId: string;
  brandName: string;
  productName: string;
  category: string;
  weightGrams: number;
  flavorName: string;
  purityPct: number | null;
  diaasScore: number | null;
  effectiveCostPerBioavailableGram: number | null;
  lowestPriceInr: number;
  bestPlatform: string;
  isEasyDigest: boolean;
  hasFssaiWarning: boolean;
  ocrVerified: boolean;
  nutritionStatus?: NutritionStatus;
  lastObservedAt?: string;
  trustScore?: number;
  authenticityScore?: number;
  labVerified?: boolean;
  affiliateUrl?: string;
  costPer100gProtein?: number | null;
  proteinPerServingGrams?: number | null;
  carbsPerServingGrams?: number | null;
  fatPerServingGrams?: number | null;
  servingSizeGrams?: number | null;
  fairyDusted?: boolean;
  isGlitchPrice?: boolean;
}
