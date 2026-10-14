export interface ProductItem {
  id: string | number;
  name: string;
  brand?: string;
  type?: string;
  price: number;
  oldPrice?: number;
  servingPrice?: number;
  proteinPerServing?: number;
  servingSizeGrams?: number;
  purityPct?: number;
  weightGrams?: number;
  image?: string;
  isVerified?: boolean;
  tag?: string;
  productUrl?: string;
}

export type SortOption = "featured" | "price-asc" | "price-desc" | "value-asc" | "purity-desc";

export type ViewMode = "consumer" | "terminal";

export interface FilterState {
  query: string;
  category: string;
  formulations: string[]; // Gate 1: whey_isolate, whey_concentrate, whey_blend, plant, casein
  maxCostPer100gProtein: number; // Gate 2: True value filter (default 600)
  selectedBrands: string[];
  maxPrice: number;
  verifiedOnly: boolean; // Gate 3: 3rd-party lab verified
  minPurityPct: number; // Gate 3: e.g. 75%
  authorizedOnly: boolean; // Gate 3: Authorized sellers only
  digestiveEnzymesOnly: boolean; // Gate 4: Digestive enzymes added
  sugarFreeOnly: boolean; // Gate 4: Zero added sugar
  unflavoredOnly: boolean; // Gate 4: Unflavored / raw only
  sort: SortOption;
}

export interface StoreOffer {
  id: string;
  retailerName: string;
  platform: string;
  sellerName: string;
  price: number;
  shippingPrice: number;
  shippingLabel: string;
  deliveryEta: string;
  isLowestVerified: boolean;
  isAuthorized: boolean;
  isGreyMarket: boolean;
  authenticityNote: string;
  returnPolicy: string;
  warningNote?: string;
  buyUrl: string;
  inStock: boolean;
}
