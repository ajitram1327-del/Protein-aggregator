export type ProteinCategory =
  | "whey_concentrate"
  | "whey_isolate"
  | "whey_blend"
  | "casein"
  | "plant"
  | "mass_gainer";

export type PlatformName =
  | "amazon_in"
  | "flipkart"
  | "healthkart"
  | "hyuga"
  | "blinkit"
  | "zepto"
  | "instamart"
  | "d2c";

export interface Product {
  id: string;
  brand_name: string;
  product_name: string;
  category: ProteinCategory;
  baseline_diaas_score: number;
  ingredients: string[];
  fssai_license_number: string;
  fssai_warning_active: boolean;
  is_active: boolean;
}

export interface ProductVariant {
  id: string;
  product_id: string;
  variant_hash: string;
  flavor_name: string;
  is_unflavored: boolean;
  weight_grams: number;
  label_protein_per_serving_g: number;
  label_serving_size_g: number;
  label_total_servings: number;
  detected_enzymes: string[];
  is_active: boolean;
}

export interface ScrapedListing {
  id: string;
  variant_id: string;
  platform_name: PlatformName;
  current_price_inr: number;
  listing_url: string;
  is_in_stock: boolean;
  is_authorized_seller: boolean;
  shipping: "prime" | "fbf" | "hk_verified" | "standard" | "instant";
  scraped_at: string;
}

export interface LabAuditReport {
  id: string;
  product_id: string;
  tested_protein_per_serving_g: number;
  batch_number: string;
  tested_at: string;
  lab_name: string;
  report_url: string;
  passed: boolean;
}

export interface ReviewAuditSummary {
  id: string;
  product_id: string;
  total_reviews: number;
  unverified_ratio: number;
  repetitive_phrase_ratio: number;
  burst_score: number;
  updated_at: string;
}

export interface ClearanceItem {
  id: string;
  variant_id: string;
  platform_name: PlatformName;
  current_price_inr: number;
  expiry_date: string;
  listing_url: string;
  is_in_stock: boolean;
  scraped_at: string;
}

export interface ProductBundle {
  product: Product;
  variants: ProductVariant[];
  listings: ScrapedListing[];
  labTest?: LabAuditReport;
  reviewStats?: ReviewAuditSummary;
}
