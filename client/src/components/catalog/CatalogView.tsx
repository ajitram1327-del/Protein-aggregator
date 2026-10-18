"use client";

import React, { useState, useMemo, useEffect, Fragment } from "react";
import Link from "next/link";
import {
  LayoutGrid,
  Terminal,
  ArrowLeft,
  ChevronDown,
  SlidersHorizontal,
  Search,
  Bell,
  Calculator,
  X,
} from "lucide-react";
import { GroupedProduct, DbVariant, CANONICAL_CATEGORIES } from "@/components/ProductBrowser";
import { DecathlonSidebar } from "./DecathlonSidebar";
import { SneakopediaCard } from "./SneakopediaCard";
import { SneakopediaProductMatrix } from "./SneakopediaProductMatrix";
import { FilterState, ViewMode, SortOption } from "./types";
import { CompareTray, CompareItem } from "@/components/CompareTray";
import { formatInr, costPer100gProtein, purityPct, computeCategoryMetrics } from "@/lib/analytics";
import { LiveMarketPulse } from "@/components/common/LiveMarketPulse";
import { TrueProteinCostCalculator } from "@/components/calculator/TrueProteinCostCalculator";
import { PriceAlertModal } from "@/components/common/PriceAlertModal";

interface CatalogViewProps {
  initialProducts: GroupedProduct[];
  initialCategory?: string;
}

export function CatalogView({ initialProducts, initialCategory }: CatalogViewProps) {
  // Initialize from URL search parameters if available
  const [filters, setFilters] = useState<FilterState>(() => {
    if (typeof window !== "undefined") {
      const p = new URLSearchParams(window.location.search);
      const brands = p.get("brand") ? [p.get("brand")!] : p.get("brands") ? p.get("brands")!.split(",") : [];
      const forms = p.get("formulations") ? p.get("formulations")!.split(",") : [];
      return {
        query: p.get("q") || p.get("search") || "",
        category: p.get("category") || initialCategory || "",
        formulations: forms,
        maxCostPer100gProtein: p.get("maxCost") ? Number(p.get("maxCost")) : 600,
        selectedBrands: brands,
        maxPrice: p.get("maxPrice") ? Number(p.get("maxPrice")) : 15000,
        verifiedOnly: p.get("verified") === "true",
        minPurityPct: p.get("minPurity") ? Number(p.get("minPurity")) : 0,
        authorizedOnly: p.get("authorized") === "true",
        digestiveEnzymesOnly: p.get("enzymes") === "true",
        sugarFreeOnly: p.get("sugarFree") === "true",
        unflavoredOnly: p.get("unflavored") === "true",
        sort: (p.get("sort") as SortOption) || "featured",
      };
    }
    return {
      query: "",
      category: initialCategory || "",
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
    };
  });

  const [searchInputValue, setSearchInputValue] = useState(filters.query);
  const [isMobileFilterOpen, setIsMobileFilterOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("consumer");
  const [isAlertOpen, setIsAlertOpen] = useState(false);
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);

  // Sneakopedia Matrix State
  const [matrixOpen, setMatrixOpen] = useState(false);
  const [matrixProduct, setMatrixProduct] = useState<GroupedProduct | null>(null);
  const [matrixVariant, setMatrixVariant] = useState<DbVariant | null>(null);

  // Compare Tray State
  const [compareItems, setCompareItems] = useState<CompareItem[]>([]);
  const [expandedTerminalRows, setExpandedTerminalRows] = useState<Set<string>>(new Set());

  // 300ms Debounce for search query input
  useEffect(() => {
    const handler = setTimeout(() => {
      setFilters((prev) => {
        if (prev.query === searchInputValue) return prev;
        return { ...prev, query: searchInputValue };
      });
    }, 300);

    return () => clearTimeout(handler);
  }, [searchInputValue]);

  // Synchronize filter state changes to URL search parameters
  useEffect(() => {
    if (typeof window === "undefined") return;

    const currentUrl = new URL(window.location.href);
    const params = currentUrl.searchParams;

    if (filters.query) params.set("search", filters.query);
    else params.delete("search");
    params.delete("q");

    if (filters.category) params.set("category", filters.category);
    else params.delete("category");

    if (filters.selectedBrands.length > 0) params.set("brand", filters.selectedBrands[0]);
    else params.delete("brand");

    if (filters.formulations.length > 0) params.set("formulations", filters.formulations.join(","));
    else params.delete("formulations");

    if (filters.sort && filters.sort !== "featured") params.set("sort", filters.sort);
    else params.delete("sort");

    if (filters.maxPrice < 15000) params.set("maxPrice", filters.maxPrice.toString());
    else params.delete("maxPrice");

    if (filters.verifiedOnly) params.set("verified", "true");
    else params.delete("verified");

    const newSearch = params.toString();
    const newRelativePath = `${window.location.pathname}${newSearch ? `?${newSearch}` : ""}`;
    window.history.replaceState({}, "", newRelativePath);
  }, [filters]);

  // Browser back/forward (popstate) restoration
  useEffect(() => {
    const handlePopState = () => {
      if (typeof window === "undefined") return;
      const p = new URLSearchParams(window.location.search);
      const query = p.get("search") || p.get("q") || "";
      const cat = p.get("category") || "";
      const brand = p.get("brand");
      const sort = (p.get("sort") as SortOption) || "featured";

      setSearchInputValue(query);
      setFilters((prev) => ({
        ...prev,
        query,
        category: cat,
        selectedBrands: brand ? [brand] : [],
        sort,
      }));
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Deep link to product modal if specified in URL on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const productParam = params.get("product");
      const variantParam = params.get("variant");

      if (productParam) {
        const foundProduct = initialProducts.find(
          (p) =>
            p.id.toLowerCase() === productParam.toLowerCase() ||
            p.baseProductName.toLowerCase() === productParam.toLowerCase()
        );
        if (foundProduct) {
          const foundVariant = variantParam
            ? foundProduct.variants.find((v) => v.id.toLowerCase() === variantParam.toLowerCase()) ||
              foundProduct.variants[0]
            : foundProduct.variants[0];
          if (foundVariant) {
            setTimeout(() => {
              setMatrixProduct(foundProduct);
              setMatrixVariant(foundVariant);
              setMatrixOpen(true);
            }, 0);
          }
        }
      }
    }
  }, [initialProducts]);

  const toggleTerminalRow = (id: string) => {
    setExpandedTerminalRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleOpenMatrix = (product: GroupedProduct, variant: DbVariant) => {
    setMatrixProduct(product);
    setMatrixVariant(variant);
    setMatrixOpen(true);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("product", product.id);
      url.searchParams.set("variant", variant.id);
      window.history.replaceState({}, "", url.toString());
    }
  };

  const handleCloseMatrix = () => {
    setMatrixOpen(false);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("product");
      url.searchParams.delete("variant");
      window.history.replaceState({}, "", url.toString());
    }
  };

  const handleSelectMatrixVariant = (variant: DbVariant) => {
    setMatrixVariant(variant);
    if (typeof window !== "undefined" && matrixProduct) {
      const url = new URL(window.location.href);
      url.searchParams.set("variant", variant.id);
      window.history.replaceState({}, "", url.toString());
    }
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
          effectiveCost: variant.best_value_metric ?? undefined,
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

  const activeCategoryConfig = useMemo(() => {
    if (!filters.category) return null;
    return (
      CANONICAL_CATEGORIES.find(
        (c) =>
          c.id === filters.category.toLowerCase() ||
          c.siloAliases.includes(filters.category.toLowerCase())
      ) || null
    );
  }, [filters.category]);

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

  // Filter Pipeline
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

        // Category Silo Match
        if (filters.category) {
          const catLower = filters.category.toLowerCase();
          const targetConfig = CANONICAL_CATEGORIES.find(
            (c) => c.id === catLower || c.siloAliases.includes(catLower)
          );
          if (targetConfig) {
            const matchesSilo = targetConfig.siloAliases.includes(g.categorySilo.toLowerCase());
            const matchesName = targetConfig.siloAliases.some((alias) =>
              `${g.baseProductName} ${g.proteinSource}`.toLowerCase().includes(alias)
            );
            if (!matchesSilo && !matchesName) return false;
          } else if (g.categorySilo.toLowerCase() !== catLower) {
            return false;
          }
        }

        // Formulations
        if (filters.formulations && filters.formulations.length > 0) {
          const haystack = `${g.baseProductName} ${g.categorySilo} ${g.proteinSource}`.toLowerCase();
          const matchesAnyFormulation = filters.formulations.some((f) => {
            if (f === "isolate") return haystack.includes("isolate");
            if (f === "concentrate") return haystack.includes("concentrate");
            if (f === "blend")
              return haystack.includes("blend") || (!haystack.includes("isolate") && haystack.includes("whey"));
            if (f === "plant")
              return (
                haystack.includes("plant") ||
                haystack.includes("pea") ||
                haystack.includes("soy") ||
                haystack.includes("vegan")
              );
            if (f === "casein") return haystack.includes("casein");
            return false;
          });
          if (!matchesAnyFormulation) return false;
        }

        // True Value (₹ / 100g Pure Protein)
        const bestVariant = g.variants[0];
        const rawServingSize = bestVariant?.label_serving_size_g ?? null;
        const rawProteinG = bestVariant?.label_protein_per_serving_g ?? null;
        const hasValidNutrition = rawServingSize && rawProteinG && rawServingSize > 0 && rawProteinG > 0 && rawProteinG <= rawServingSize;

        if (filters.maxCostPer100gProtein < 600) {
          if (!hasValidNutrition) return false;
          const totalServings = Math.max(1, Math.round((bestVariant?.weight_grams || 1000) / rawServingSize!));
          const cost100g = costPer100gProtein(g.lowestPrice, totalServings, rawProteinG!);
          if (!isFinite(cost100g) || cost100g > filters.maxCostPer100gProtein) return false;
        }

        // Verification & Purity
        if (filters.verifiedOnly && !g.labVerified) return false;

        if (filters.minPurityPct > 0) {
          const maxPurity = Math.max(
            ...g.variants.map((v) => {
              if (v.calculated_purity_pct !== null && v.calculated_purity_pct !== undefined) {
                return v.calculated_purity_pct;
              }
              if (v.label_protein_per_serving_g && v.label_serving_size_g && v.label_serving_size_g > 0) {
                return purityPct(v.label_protein_per_serving_g, v.label_serving_size_g);
              }
              return 0;
            })
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

        // Dietary
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

        // Brands
        if (filters.selectedBrands.length > 0 && !filters.selectedBrands.includes(g.brand)) {
          return false;
        }

        // Price
        if (g.lowestPrice > filters.maxPrice && g.lowestPrice !== Infinity) {
          return false;
        }

        return true;
      })
      .sort((a, b) => {
        const getEffectiveMetric = (item: GroupedProduct) => {
          if (item.bestValueMetric && item.bestValueMetric > 0 && isFinite(item.bestValueMetric)) {
            return item.bestValueMetric;
          }
          const v0 = item.variants[0];
          const rawServing = v0?.label_serving_size_g;
          const rawProt = v0?.label_protein_per_serving_g;
          if (rawServing && rawProt && rawServing > 0 && rawProt > 0 && rawProt <= rawServing) {
            const servings = Math.max(1, Math.round((v0?.weight_grams || 1000) / rawServing));
            return costPer100gProtein(item.lowestPrice, servings, rawProt) || Infinity;
          }
          return Infinity;
        };

        const metricA = getEffectiveMetric(a);
        const metricB = getEffectiveMetric(b);

        if (filters.sort === "value-asc") return metricA - metricB;
        if (filters.sort === "price-asc") return a.lowestPrice - b.lowestPrice;
        if (filters.sort === "price-desc") return b.lowestPrice - a.lowestPrice;
        if (filters.sort === "purity-desc") {
          const purityA = a.variants[0]?.calculated_purity_pct || 0;
          const purityB = b.variants[0]?.calculated_purity_pct || 0;
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
      {/* 0. Live Drops Ticker Strip */}
      <LiveMarketPulse onOpenAlertModal={() => setIsAlertOpen(true)} />

      {/* 1. Category & Silo Secondary Sub-Bar */}
      <div className="border-b border-slate-200 px-4 sm:px-6 py-2.5 sticky top-16 bg-white/95 backdrop-blur-md z-40 shadow-xs">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto gap-4">
          <div className="flex items-center gap-2 text-xs font-mono">
            <Link
              href="/"
              className="text-slate-500 hover:text-slate-900 flex items-center gap-1 font-semibold"
            >
              <ArrowLeft className="size-3" /> Home
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-bold truncate">Catalog Terminal</span>
          </div>

          {/* Category Quick Switcher */}
          <div className="hidden md:flex items-center gap-1 overflow-x-auto">
            <button
              type="button"
              onClick={() => {
                setFilters((prev) => ({ ...prev, category: "" }));
                if (typeof window !== "undefined") window.history.pushState({}, "", "/catalog");
              }}
              className={`px-3 py-1 text-xs font-mono font-bold rounded-sm border transition-colors ${
                !filters.category
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 text-slate-700 hover:text-slate-900 bg-white"
              }`}
            >
              All
            </button>
            {CANONICAL_CATEGORIES.map((cat) => {
              const isActive =
                filters.category.toLowerCase() === cat.id ||
                cat.siloAliases.includes(filters.category.toLowerCase());
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => {
                    setFilters((prev) => ({ ...prev, category: cat.id }));
                    if (typeof window !== "undefined") {
                      window.history.pushState({}, "", `/catalog?category=${cat.id}`);
                    }
                  }}
                  className={`px-3 py-1 text-xs font-mono font-semibold rounded-sm border transition-colors ${
                    isActive
                      ? cat.activePill + " font-bold shadow-xs"
                      : "border-slate-200 text-slate-700 hover:text-slate-900 bg-white"
                  }`}
                >
                  {cat.title}
                </button>
              );
            })}
          </div>

          {/* Right Action Controls: Calculator, Alert & View Switcher */}
          <div className="flex items-center gap-2">
            <Link
              href="/calculator"
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-bold text-slate-700 bg-white border border-slate-300 hover:border-slate-800 rounded-sm transition-colors shadow-xs"
              title="True Protein Cost & Yield Calculator"
            >
              <Calculator className="size-3.5 text-emerald-700" />
              <span className="hidden md:inline">Calculator</span>
            </Link>

            <Link
              href="/alerts"
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-bold text-slate-700 bg-white border border-slate-300 hover:border-slate-800 rounded-sm transition-colors shadow-xs"
              title="Set Price Drop Alert"
            >
              <Bell className="size-3.5 text-emerald-700" />
              <span className="hidden lg:inline">Alert</span>
            </Link>

            {/* Mode Switcher Toggle */}
            <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-sm border border-slate-200">
              <button
                type="button"
                onClick={() => setViewMode("consumer")}
                className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-sm text-xs font-mono font-bold transition-colors ${
                  viewMode === "consumer"
                    ? "bg-white text-slate-900 shadow-xs border border-slate-200"
                    : "text-slate-500 hover:text-slate-900"
                }`}
              >
                <LayoutGrid className="size-3.5" />
                <span className="hidden sm:inline">Cards</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("terminal")}
                className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-sm text-xs font-mono font-bold transition-colors ${
                  viewMode === "terminal"
                    ? "bg-slate-900 text-white shadow-xs"
                    : "text-slate-500 hover:text-slate-900"
                }`}
              >
                <Terminal className="size-3.5 text-emerald-400" />
                <span className="hidden sm:inline">Table</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Screener Controls Bar */}
      <section className="border-b border-slate-200 bg-white py-3 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 max-w-xl">
            {/* Mobile Filter Button */}
            <button
              type="button"
              onClick={() => setIsMobileFilterOpen(true)}
              className="lg:hidden flex items-center gap-1.5 px-3 py-2 border border-slate-300 rounded-sm text-xs font-mono font-bold text-slate-700 hover:bg-slate-50 shrink-0"
            >
              <SlidersHorizontal className="size-3.5" />
              <span>Filters</span>
            </button>

            {/* Search Input with Debounced Binding */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchInputValue}
                onChange={(e) => setSearchInputValue(e.target.value)}
                placeholder="Search supplements, brand, or flavor..."
                aria-label="Search catalog"
                className="w-full pl-9 pr-3 py-1.5 text-xs font-mono border border-slate-200 rounded-sm outline-none focus:border-slate-900"
              />
            </div>
          </div>

          {/* Results count & Sort */}
          <div className="flex items-center justify-between sm:justify-end gap-3 text-xs font-mono">
            <span className="text-slate-500">
              Showing <strong className="text-slate-900">{displayedGroups.length}</strong> Products
            </span>

            <div className="relative">
              <select
                aria-label="Sort products"
                value={filters.sort}
                onChange={(e) => setFilters((prev) => ({ ...prev, sort: e.target.value as SortOption }))}
                className="h-8 appearance-none rounded-sm border border-slate-300 bg-white pl-2.5 pr-7 text-xs font-mono font-bold uppercase tracking-wider text-slate-800 outline-none cursor-pointer"
              >
                <option value="featured">Featured (Verified First)</option>
                <option value="value-asc">Best Value (₹/100g Prot)</option>
                <option value="price-asc">Price: Low to High</option>
                <option value="price-desc">Price: High to Low</option>
                <option value="purity-desc">Highest Purity %</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3 -translate-y-1/2 text-slate-400" />
            </div>
          </div>
        </div>
      </section>

      {/* 3. Main Catalog Content Area with Decathlon Sidebar */}
      <main id="main-content" className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Decathlon-Style Simple & Efficient Sidebar */}
          <DecathlonSidebar
            filters={filters}
            availableCategories={availableCategories}
            availableBrands={availableBrands}
            totalMatches={displayedGroups.length}
            isMobileOpen={isMobileFilterOpen}
            onFilterChange={(partial) => setFilters((prev) => ({ ...prev, ...partial }))}
            onResetFilters={resetAllFilters}
            onCloseMobile={() => setIsMobileFilterOpen(false)}
          />

          {/* Product Grid / Terminal Screener */}
          <div className="flex-1 min-w-0">
            {displayedGroups.length === 0 ? (
              <div className="flex min-h-[350px] flex-col items-center justify-center rounded-sm border border-dashed border-slate-300 bg-white p-8 text-center font-mono">
                <div className="size-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 mb-3">
                  <Search className="size-5" />
                </div>
                <p className="text-base font-bold text-slate-900">
                  No supplements matched your filter criteria
                </p>
                <div className="mt-2 text-xs text-slate-500 max-w-md">
                  Active constraints causing zero matches:
                  <div className="flex flex-wrap gap-1 justify-center mt-2">
                    {filters.query && (
                      <span className="bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-xs text-[11px] font-bold text-slate-800">
                        Query: &quot;{filters.query}&quot;
                      </span>
                    )}
                    {filters.category && (
                      <span className="bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-xs text-[11px] font-bold text-slate-800">
                        Category: {filters.category}
                      </span>
                    )}
                    {filters.selectedBrands.length > 0 && (
                      <span className="bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-xs text-[11px] font-bold text-slate-800">
                        Brands: {filters.selectedBrands.join(", ")}
                      </span>
                    )}
                    {filters.formulations.length > 0 && (
                      <span className="bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-xs text-[11px] font-bold text-slate-800">
                        Forms: {filters.formulations.join(", ")}
                      </span>
                    )}
                    {filters.maxPrice < 15000 && (
                      <span className="bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-xs text-[11px] font-bold text-slate-800">
                        Max Price: ₹{filters.maxPrice}
                      </span>
                    )}
                    {filters.verifiedOnly && (
                      <span className="bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-xs text-[11px] font-bold text-emerald-800">
                        Verified Only
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={resetAllFilters}
                  className="mt-5 rounded-sm bg-slate-900 px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-white hover:bg-slate-800 transition-colors"
                >
                  Clear all filters
                </button>
              </div>
            ) : viewMode === "consumer" ? (
              /* Sneakopedia-Style Clean Minimalist Card Grid (Image 4) */
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {displayedGroups.map((product) => (
                  <SneakopediaCard
                    key={product.id}
                    product={product}
                    onOpenMatrix={handleOpenMatrix}
                    onToggleCompareTray={handleToggleCompare}
                    isTraySelected={compareItems.some((i) =>
                      product.variants.some((v) => v.id === i.variantId)
                    )}
                  />
                ))}
              </div>
            ) : (
              /* Terminal Mode Monospace Screener Table */
              <div className="border border-slate-300 bg-white shadow-xs overflow-x-auto font-mono text-xs rounded-sm">
                <table className="w-full text-left border-collapse">
                  <thead className="border-b bg-slate-100 uppercase text-[11px] text-slate-600">
                    <tr>
                      <th className="w-8 px-2 py-2.5 text-center" />
                      <th className="px-3 py-2.5">Instrument</th>
                      <th className="px-3 py-2.5">Category</th>
                      <th className="px-3 py-2.5 text-right">Lowest Ask</th>
                      <th className="px-3 py-2.5 text-right">
                        {activeCategoryConfig ? activeCategoryConfig.primaryHeader : "₹ / Active Yield"}
                      </th>
                      <th className="px-3 py-2.5 text-right">
                        {activeCategoryConfig ? activeCategoryConfig.secondaryHeader : "Benchmark"}
                      </th>
                      <th className="px-3 py-2.5">Quality / Flags</th>
                      <th className="px-3 py-2.5 text-right">Action</th>
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

                      const catMetrics = computeCategoryMetrics(
                        product.categorySilo,
                        product.lowestPrice,
                        bestVariant?.raw_json_data || {
                          servingSizeGrams: servingSize,
                          proteinPerServingGrams: proteinG,
                          servingsPerContainer: totalServings,
                          totalProteinPerTubGrams: proteinG * totalServings,
                          diaasScore: 1.15,
                        },
                        bestVariant?.weight_grams || 1000
                      );

                      return (
                        <Fragment key={product.id}>
                          <tr className="hover:bg-slate-50 transition-colors">
                            <td className="px-2 py-2.5 text-center">
                              <button
                                type="button"
                                onClick={() => toggleTerminalRow(product.id)}
                                className="font-bold text-slate-500 hover:text-slate-900"
                              >
                                {isExpanded ? "−" : "+"}
                              </button>
                            </td>
                            <td className="px-3 py-2.5">
                              <div className="font-bold text-slate-900">{product.brand}</div>
                              <div className="text-[11px] text-slate-500 line-clamp-1">
                                {product.baseProductName}
                              </div>
                            </td>
                            <td className="px-3 py-2.5 uppercase text-[11px] text-slate-600">
                              {product.categorySilo.replace(/_/g, " ")}
                            </td>
                            <td className="px-3 py-2.5 text-right font-bold text-slate-900 tabular-nums">
                              {formatInr(product.lowestPrice)}
                            </td>
                            <td className="px-3 py-2.5 text-right font-bold text-emerald-700">
                              {catMetrics.primaryValue}
                            </td>
                            <td className="px-3 py-2.5 text-right font-medium text-slate-700">
                              {catMetrics.secondaryValue}
                            </td>
                            <td className="px-3 py-2.5">
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
                            <td className="px-3 py-2.5 text-right">
                              <button
                                type="button"
                                onClick={() =>
                                  handleOpenMatrix(product, bestVariant || product.variants[0])
                                }
                                className="bg-slate-900 hover:bg-emerald-700 text-white px-2.5 py-1 text-[11px] font-bold uppercase transition-colors rounded-sm"
                              >
                                Matrix
                              </button>
                            </td>
                          </tr>

                          {/* Expanded Variant Sub-rows */}
                          {isExpanded &&
                            product.variants.map((v) => (
                              <tr key={v.id} className="bg-slate-50/70 border-b border-slate-200">
                                <td />
                                <td className="px-3 py-1.5 pl-6" colSpan={2}>
                                  └ {v.flavor} · {v.weight_grams}g
                                </td>
                                <td className="px-3 py-1.5 text-right font-bold tabular-nums">
                                  {formatInr(v.lowest_price_inr)}
                                </td>
                                <td className="px-3 py-1.5 text-right font-semibold text-emerald-700" colSpan={2}>
                                  Lowest Offer
                                </td>
                                <td />
                                <td className="px-3 py-1.5 text-right">
                                  <button
                                    type="button"
                                    onClick={() => handleOpenMatrix(product, v)}
                                    className="text-emerald-700 hover:underline text-[10px] font-bold"
                                  >
                                    View Stores →
                                  </button>
                                </td>
                              </tr>
                            ))}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Sneakopedia Parent-Child Matrix Modal & Price History Graph (Image 5) */}
      <SneakopediaProductMatrix
        isOpen={matrixOpen}
        onClose={handleCloseMatrix}
        product={matrixProduct}
        selectedVariant={matrixVariant}
        onSelectVariant={handleSelectMatrixVariant}
        onToggleCompareTray={handleToggleCompare}
        isTraySelected={compareItems.some((i) =>
          matrixProduct?.variants.some((v) => v.id === i.variantId)
        )}
      />

      {/* Floating Compare Tray */}
      <CompareTray
        selectedItems={compareItems}
        onRemove={(id) => setCompareItems((prev) => prev.filter((i) => i.variantId !== id))}
        onClear={() => setCompareItems([])}
      />

      {/* Price Alert Subscription Modal */}
      <PriceAlertModal
        isOpen={isAlertOpen}
        onClose={() => setIsAlertOpen(false)}
        products={initialProducts}
      />

      {/* True Protein Cost Calculator Modal */}
      {isCalculatorOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs font-sans">
          <div className="max-w-3xl w-full relative">
            <button
              type="button"
              onClick={() => setIsCalculatorOpen(false)}
              className="absolute -top-10 right-0 text-white hover:text-slate-300 font-mono text-xs font-bold uppercase tracking-wider flex items-center gap-1 transition-colors"
            >
              <X className="size-4" /> Close Calculator [ESC]
            </button>
            <TrueProteinCostCalculator />
          </div>
        </div>
      )}
    </div>
  );
}
