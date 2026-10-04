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

export type SortOption = "featured" | "price-asc" | "price-desc";

export interface FilterState {
  query: string;
  category: string;
  selectedBrands: string[];
  maxPrice: number;
  verifiedOnly: boolean;
  sort: SortOption;
}
