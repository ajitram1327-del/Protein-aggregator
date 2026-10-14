"use client";

import React, { useState, useMemo, Fragment } from "react";
import { ShoppingCart, LayoutGrid, Terminal, ShieldCheck, Zap, AlertTriangle, ArrowRight, ExternalLink } from "lucide-react";
import { ProductCard } from "./catalog/ProductCard";
import { CatalogControls } from "./catalog/CatalogControls";
import { StoreComparisonDrawer } from "./catalog/StoreComparisonDrawer";
import { FilterState, ViewMode } from "./catalog/types";
import { CompareTray, CompareItem } from "./CompareTray";
import { formatInr, costPer100gProtein, purityPct } from "@/lib/analytics";

export interface DbPriceListing {
  source: string;
  price_inr: number;
  source_url: string;
  seller_name?: string;
  is_authorized_seller?: boolean;
  is_in_stock?: boolean;
  in_stock?: boolean;
}

export interface DbVariant {
  id: string;
  sku_id: string;
  flavor: string;
  weight_grams: number;
  lowest_price_inr: number;
  best_value_metric: number;
  label_serving_size_g?: number;
  label_protein_per_serving_g?: number;
  calculated_purity_pct?: number;
  raw_json_data: any;
  price_listings: DbPriceListing[];
  has_bot_reviews?: boolean;
  authenticity_score?: number;
}

export interface GroupedProduct {
  id: string;
  brand: string;
  baseProductName: string;
  categorySilo: string;
  proteinSource: string;
  imageUrl: string;
  variants: DbVariant[];
  lowestPrice: number;
  bestValueMetric: number;
  isFairyDusted?: boolean;
  labVerified?: boolean;
  trustScore?: number;
  labReportUrl?: string;
}

export function ProductBrowser({ initialProducts }: { initialProducts: GroupedProduct[] }) {
  // 4-Gate Filter State
  const [filters, setFilters] = useState<FilterState>({
    query: "",
    category: "",
    formulations: [],
    maxCostPer100gProtein: 600,
    selectedBrands: [],
    maxPrice: 15000,
    verifiedOnly: false,
    minPurityPct: 0,
    authorizedOnly: false,
    digestiveEnzymesOnly: false,
    sugarFreeOnly: false,
    unflavoredOnly: false,
    sort: "featured",
  });

  const [isMobileFilterOpen, setIsMobileFilterOpen] = useState(false);

  // Dual View Mode: Consumer Mode vs Terminal Mode
  const [viewMode, setViewMode] = useState<ViewMode>("consumer");

  // Store Comparison Drawer State
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerProduct, setDrawerProduct] = useState<GroupedProduct | null>(null);
  const [drawerVariant, setDrawerVariant] = useState<DbVariant | null>(null);

  // Cross-Product Comparison Matrix Tray
  const [compareItems, setCompareItems] = useState<CompareItem[]>([]);

  // Terminal Row Expansion State
  const [expandedTerminalRows, setExpandedTerminalRows] = useState<Set<string>>(new Set());

  const toggleTerminalRow = (id: string) => {
    setExpandedTerminalRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleOpenCompareDrawer = (product: GroupedProduct, variant: DbVariant) => {
    setDrawerProduct(product);
    setDrawerVariant(variant);
    setDrawerOpen(true);
  };

  const handleToggleCompare = (variant: DbVariant, group: GroupedProduct) => {
    setCompareItems((prev) => {
      const exists = prev.some((i) => i.variantId === variant.id);
      if (exists) {
        return prev.filter((i) => i.variantId !== variant.id);
      }
      if (prev.length >= 4) {
        alert("Compare tray limit is 4 items max.");
        return prev;
      }
      return [
        ...prev,
        {
          variantId: variant.id,
          brand: group.brand,
          productName: group.baseProductName,
          flavor: variant.flavor,
          weightGrams: variant.weight_grams,
          effectiveCost: variant.best_value_metric,
          lowestPrice: variant.lowest_price_inr,
        },
      ];
    });
  };

  const availableCategories = useMemo(
    () => Array.from(new Set(initialProducts.map((p) => p.categorySilo).filter(Boolean))),
    [initialProducts]
  );
  const availableBrands = useMemo(
    () => Array.from(new Set(initialProducts.map((p) => p.brand).filter(Boolean))),
    [initialProducts]
  );

  const resetAllFilters = () => {
    setFilters({
      query: "",
      category: "",
      formulations: [],
      maxCostPer100gProtein: 600,
      selectedBrands: [],
      maxPrice: 15000,
      verifiedOnly: false,
      minPurityPct: 0,
      authorizedOnly: false,
      digestiveEnzymesOnly: false,
      sugarFreeOnly: false,
      unflavoredOnly: false,
      sort: "featured",
    });
  };

  // 4-Gate Decision Filter Pipeline
  const displayedGroups = useMemo(() => {
    return initialProducts
      .filter((g) => {
        // Search Query
        const queryLower = filters.query.toLowerCase().trim();
        const matchesQuery =
          !queryLower ||
          `${g.baseProductName} ${g.brand} ${g.proteinSource}`.toLowerCase().includes(queryLower) ||
          g.variants.some((v) => (v.flavor || "").toLowerCase().includes(queryLower));
        if (!matchesQuery) return false;

        // Category Silo
        if (filters.category && g.categorySilo !== filters.category) return false;

        // Gate 1: Protein Formulation Lock
        if (filters.formulations && filters.formulations.length > 0) {
          const haystack = `${g.baseProductName} ${g.categorySilo} ${g.proteinSource}`.toLowerCase();
          const matchesAnyFormulation = filters.formulations.some((f) => {
            if (f === "isolate") return haystack.includes("isolate");
            if (f === "concentrate") return haystack.includes("concentrate");
            if (f === "blend") return haystack.includes("blend") || (!haystack.includes("isolate") && haystack.includes("whey"));
            if (f === "plant") return haystack.includes("plant") || haystack.includes("pea") || haystack.includes("soy") || haystack.includes("vegan");
            if (f === "casein") return haystack.includes("casein");
            return false;
          });
          if (!matchesAnyFormulation) return false;
        }

        // Gate 2: True Value Filter (₹ / 100g Pure Protein - applies to protein powders)
        if (g.categorySilo === "protein" || !g.categorySilo) {
          const bestVariant = g.variants[0];
          const servingSize = Math.max(10, bestVariant?.label_serving_size_g || 33);
          const proteinG = Math.max(5, bestVariant?.label_protein_per_serving_g || 24);
          const totalServings = Math.max(1, Math.round((bestVariant?.weight_grams || 1000) / servingSize));
          const cost100g = costPer100gProtein(g.lowestPrice, totalServings, proteinG);

          if (filters.maxCostPer100gProtein < 600 && isFinite(cost100g)) {
            if (cost100g > filters.maxCostPer100gProtein) return false;
          }
        }

        // Gate 3: Purity & Trust Thresholds
        if (filters.verifiedOnly && !g.labVerified) return false;

        if (filters.minPurityPct > 0) {
          const maxPurity = Math.max(
            ...g.variants.map((v) =>
              v.calculated_purity_pct || purityPct(v.label_protein_per_serving_g || 24, v.label_serving_size_g || 33)
            )
          );
          if (maxPurity < filters.minPurityPct) return false;
        }

        if (filters.authorizedOnly) {
          const hasAuthorized = g.variants.some((v) =>
            v.price_listings.some((l) => l.is_authorized_seller ?? true)
          );
          if (!hasAuthorized && g.variants.some((v) => v.price_listings.length > 0)) {
            return false;
          }
        }

        // Gate 4: Dietary & Digestion Flags
        if (filters.digestiveEnzymesOnly) {
          const hasEnzymes =
            g.baseProductName.toLowerCase().includes("zyme") ||
            g.baseProductName.toLowerCase().includes("enzyme") ||
            g.variants.some(
              (v) =>
                v.raw_json_data?.has_digestive_enzymes ||
                (v.raw_json_data?.detected_enzymes && v.raw_json_data.detected_enzymes.length > 0)
            );
          if (!hasEnzymes) return false;
        }

        if (filters.sugarFreeOnly) {
          const isSugarFree =
            !g.baseProductName.toLowerCase().includes("sugar") &&
            !g.baseProductName.toLowerCase().includes("gainer");
          if (!isSugarFree) return false;
        }

        if (filters.unflavoredOnly) {
          const hasUnflavored = g.variants.some(
            (v) =>
              (v.flavor || "").toLowerCase().includes("unflavor") ||
              (v.flavor || "").toLowerCase().includes("raw")
          );
          if (!hasUnflavored) return false;
        }

        // Brand Match
        if (filters.selectedBrands.length > 0 && !filters.selectedBrands.includes(g.brand)) {
          return false;
        }

        // Max Sticker Price
        if (g.lowestPrice > filters.maxPrice && g.lowestPrice !== Infinity) {
          return false;
        }

        return true;
      })
      .sort((a, b) => {
        // Silo-aware Equalizer metric resolver (preserves PRD metric per silo)
        const getEffectiveMetric = (item: GroupedProduct) => {
          if (item.bestValueMetric && item.bestValueMetric > 0 && isFinite(item.bestValueMetric)) {
            return item.bestValueMetric;
          }
          const v0 = item.variants[0];
          const weight = v0?.weight_grams || 1000;
          const sSize = v0?.label_serving_size_g || 33;
          const prot = v0?.label_protein_per_serving_g || 24;
          const servings = Math.max(1, Math.round(weight / sSize));
          return costPer100gProtein(item.lowestPrice, servings, prot) || Infinity;
        };

        const metricA = getEffectiveMetric(a);
        const metricB = getEffectiveMetric(b);

        if (filters.sort === "value-asc") return metricA - metricB;
        if (filters.sort === "price-asc") return a.lowestPrice - b.lowestPrice;
        if (filters.sort === "price-desc") return b.lowestPrice - a.lowestPrice;
        if (filters.sort === "purity-desc") {
          const purityA = a.variants[0]?.calculated_purity_pct || 75;
          const purityB = b.variants[0]?.calculated_purity_pct || 75;
          return purityB - purityA;
        }

        // Featured: Verified first, then best value metric
        if (a.labVerified !== b.labVerified) {
          return a.labVerified ? -1 : 1;
        }
        return metricA - metricB;
      });
  }, [initialProducts, filters]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-32">
      {/* Navigation & Mode Switcher */}
      <nav className="border-b border-slate-200 px-4 sm:px-6 py-3.5 sticky top-0 bg-white/95 backdrop-blur-xl z-40 shadow-sm">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto gap-4">
          <div
            className="font-black text-2xl tracking-tighter text-slate-900 italic cursor-pointer flex items-center"
            onClick={() => window.location.href = "/"}
          >
            <span className="text-emerald-600">PROTE</span>INDEX
          </div>

          {/* Mode Switcher Toggle */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              type="button"
              onClick={() => setViewMode("consumer")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                viewMode === "consumer"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <LayoutGrid className="size-3.5" />
              <span>Consumer</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("terminal")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                viewMode === "terminal"
                  ? "bg-slate-900 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <Terminal className="size-3.5 text-emerald-400" />
              <span>Terminal</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Main Catalog View */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="lg:grid lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-8">
          
          {/* 4-Gate Filter Controls */}
          <CatalogControls
            filters={filters}
            availableCategories={availableCategories}
            availableBrands={availableBrands}
            totalMatches={displayedGroups.length}
            isMobileFilterOpen={isMobileFilterOpen}
            onFilterChange={(partial) => setFilters((prev) => ({ ...prev, ...partial }))}
            onResetFilters={resetAllFilters}
            setIsMobileFilterOpen={setIsMobileFilterOpen}
          />

          {/* Content Area */}
          <section className="mt-6 lg:mt-0">
            {displayedGroups.length === 0 ? (
              <div className="flex min-h-[350px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm">
                <p className="text-base font-bold text-slate-800 font-mono">
                  No products matched your decision criteria
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Try adjusting the ₹/100g pure protein slider or relaxing formulation locks.
                </p>
                <button
                  type="button"
                  onClick={resetAllFilters}
                  className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-white hover:bg-slate-800 transition-colors"
                >
                  Reset all gates
                </button>
              </div>
            ) : viewMode === "consumer" ? (
              /* Consumer Mode: Dynamic In-Card State Machine Grid */
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {displayedGroups.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onOpenCompareDrawer={handleOpenCompareDrawer}
                    onToggleCompareTray={handleToggleCompare}
                    isTraySelected={compareItems.some((i) =>
                      product.variants.some((v) => v.id === i.variantId)
                    )}
                  />
                ))}
              </div>
            ) : (
              /* Terminal Mode: High-Density Monospace Financial Screener */
              <div className="border border-slate-300 bg-white shadow-sm overflow-x-auto font-mono text-xs">
                <table className="w-full text-left border-collapse">
                  <thead className="border-b bg-slate-100/80 uppercase text-[11px] text-slate-600">
                    <tr>
                      <th className="w-8 px-2 py-2 text-center" />
                      <th className="px-3 py-2">Instrument</th>
                      <th className="px-3 py-2">Silo</th>
                      <th className="px-3 py-2 text-right">Lowest Ask</th>
                      <th className="px-3 py-2 text-right">₹/100g Prot</th>
                      <th className="px-3 py-2 text-right">Purity</th>
                      <th className="px-3 py-2">Flags</th>
                      <th className="px-3 py-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {displayedGroups.map((product) => {
                      const isExpanded = expandedTerminalRows.has(product.id);
                      const bestVariant = product.variants[0];
                      const servingSize = Math.max(10, bestVariant?.label_serving_size_g || 33);
                      const proteinG = Math.max(5, bestVariant?.label_protein_per_serving_g || 24);
                      const totalServings = Math.max(
                        1,
                        Math.round((bestVariant?.weight_grams || 1000) / servingSize)
                      );
                      const cost100g = costPer100gProtein(product.lowestPrice, totalServings, proteinG);
                      const purity = bestVariant?.calculated_purity_pct || purityPct(proteinG, servingSize);

                      return (
                        <Fragment key={product.id}>
                          <tr className="hover:bg-slate-50 transition-colors">
                            <td className="px-2 py-2 text-center">
                              <button
                                type="button"
                                onClick={() => toggleTerminalRow(product.id)}
                                className="font-bold text-slate-500 hover:text-slate-900"
                              >
                                {isExpanded ? "−" : "+"}
                              </button>
                            </td>
                            <td className="px-3 py-2">
                              <div className="font-bold text-slate-900">{product.brand}</div>
                              <div className="text-[11px] text-slate-500 line-clamp-1">
                                {product.baseProductName}
                              </div>
                            </td>
                            <td className="px-3 py-2 uppercase text-[11px] text-slate-600">
                              {product.categorySilo.replace(/_/g, " ")}
                            </td>
                            <td className="px-3 py-2 text-right font-bold text-slate-900">
                              {formatInr(product.lowestPrice)}
                            </td>
                            <td className="px-3 py-2 text-right font-bold text-emerald-700">
                              {formatInr(cost100g)}
                            </td>
                            <td className="px-3 py-2 text-right">
                              {purity.toFixed(1)}%
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-1">
                                {product.labVerified && (
                                  <span className="border border-emerald-600 text-emerald-700 px-1 text-[9px] font-bold">
                                    LAB ✓
                                  </span>
                                )}
                                {product.isFairyDusted && (
                                  <span className="border border-amber-600 text-amber-700 px-1 text-[9px] font-bold">
                                    FILLER
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-right">
                              <button
                                type="button"
                                onClick={() =>
                                  handleOpenCompareDrawer(product, bestVariant || product.variants[0])
                                }
                                className="bg-slate-900 hover:bg-emerald-700 text-white px-2.5 py-1 text-[11px] font-bold uppercase transition-colors"
                              >
                                Stores
                              </button>
                            </td>
                          </tr>

                          {/* Expanded Variant Sub-rows */}
                          {isExpanded &&
                            product.variants.map((v) => {
                              const vServings = Math.max(
                                1,
                                Math.round((v.weight_grams || 1000) / (v.label_serving_size_g || 33))
                              );
                              const vProt = v.label_protein_per_serving_g || 24;
                              const vCost100g = costPer100gProtein(v.lowest_price_inr, vServings, vProt);

                              return (
                                <tr key={v.id} className="bg-slate-50/70 border-b border-slate-200">
                                  <td />
                                  <td className="px-3 py-1.5 pl-6" colSpan={2}>
                                    └ {v.flavor} · {v.weight_grams}g · {vServings} scoops
                                  </td>
                                  <td className="px-3 py-1.5 text-right font-bold">
                                    {formatInr(v.lowest_price_inr)}
                                  </td>
                                  <td className="px-3 py-1.5 text-right font-semibold text-emerald-700">
                                    {formatInr(vCost100g)}
                                  </td>
                                  <td colSpan={2} />
                                  <td className="px-3 py-1.5 text-right">
                                    <button
                                      type="button"
                                      onClick={() => handleOpenCompareDrawer(product, v)}
                                      className="text-emerald-700 hover:underline text-[10px] font-bold"
                                    >
                                      Inspect Stores →
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* Slide-Over Store Comparison Drawer */}
      <StoreComparisonDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        product={drawerProduct}
        selectedVariant={drawerVariant}
        onSelectVariant={(v) => setDrawerVariant(v)}
      />

      {/* Floating Compare Tray for Cross-Product Comparison */}
      <CompareTray
        selectedItems={compareItems}
        onRemove={(id) => setCompareItems((prev) => prev.filter((i) => i.variantId !== id))}
        onClear={() => setCompareItems([])}
      />
    </div>
  );
}
