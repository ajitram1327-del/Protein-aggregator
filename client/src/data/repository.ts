import type { ClearanceItem, ProductBundle } from "./types";

export interface DataRepository {
  getAllBundles(): Promise<ProductBundle[]>;
  getBundleById(id: string): Promise<ProductBundle | null>;
  getClearanceDeals(): Promise<(ClearanceItem & { bundle: ProductBundle })[]>;
}
