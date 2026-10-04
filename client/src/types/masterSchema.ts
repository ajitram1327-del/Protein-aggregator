/**
 * Master Universal JSON Schema Contract (Proteindex PRD v2.1 Section 2)
 * Uniform data contract consumed across RESTful APIs and frontend screeners.
 */

export interface PackagingInfo {
  weightGrams: number;
  servingsCount: number;
  servingSizeGrams: number;
}

export interface NutritionalProfile {
  activeIngredientPerServingGrams: number;
  pdcaasScore: number;
  bioavailableProteinPerServing: number;
  proteinPurityPct: number;
  caloriesPerServing: number;
  carbsPerServingGrams: number;
}

export interface UsefulDoseAnalysis {
  leucinePerServingGrams: number;
  meetsMpsThreshold: boolean;
  aminoSpikeRisk: boolean;
  fillersDetected: string[];
}

export interface EqualizerMetrics {
  primaryMetricLabel: string;
  primaryMetricValue: number;
  secondaryMetricLabel: string;
  secondaryMetricValue: number;
}

export interface VendorOffer {
  platform: string;
  url: string;
  priceInr: number;
  inStock?: boolean;
  sellerName?: string;
  isAuthorizedSeller?: boolean;
}

export interface PricingSummary {
  lowestPriceInr: number;
  lowestAuthorizedPriceInr?: number;
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
  purityPct: number;
  diaasScore: number;
  effectiveCostPerBioavailableGram: number;
  lowestPriceInr: number;
  bestPlatform: string;
  isEasyDigest: boolean;
  hasFssaiWarning: boolean;
  ocrVerified: boolean;
  trustScore?: number;
  authenticityScore?: number;
  labVerified?: boolean;
  affiliateUrl?: string;
}
