import { SupabaseRepository } from "./supabase-repository";
import type { DataRepository } from "./repository";

// Single active repository wired directly to live Supabase DB
export const repository: DataRepository = new SupabaseRepository();

export async function getBundles() {
  return repository.getAllBundles();
}

export async function getBundleById(id: string) {
  return repository.getBundleById(id);
}

export async function getClearanceDeals() {
  return repository.getClearanceDeals();
}
