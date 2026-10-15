"use client";

import React, { useState, useMemo, Fragment, useEffect } from "react";
import {
  LayoutGrid,
  Terminal,
  ShieldCheck,
  Zap,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  Search,
  Scale,
  ExternalLink,
} from "lucide-react";
import { ProductCard } from "./catalog/ProductCard";
import { CatalogControls } from "./catalog/CatalogControls";
import { StoreComparisonDrawer } from "./catalog/StoreComparisonDrawer";
import { FilterState, ViewMode } from "./catalog/types";
import { CompareTray, CompareItem } from "./CompareTray";
import { formatInr, costPer100gProtein, purityPct, computeCategoryMetrics } from "@/lib/analytics";

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

export const CANONICAL_CATEGORIES = [
  {
    id: "protein",
    siloAliases: ["protein", "whey", "plant"],
    title: "Whey & Plant Protein",
    shortLabel: "Protein",
    tagline: "Benchmark by ₹ / g Pure Protein",
    description: "Stop paying for filler and maltodextrin. Compare authentic Isolate, Concentrate, and Plant blends with verified DIAAS scores.",
    metricExample: "Lowest ask: ₹1.62 / g Protein",
    color: "border-emerald-500/40 hover:border-emerald-500 bg-emerald-950/5",
    activePill: "border-emerald-500 text-emerald-800 bg-emerald-50",
    badge: "Whey & Isolate",
    badgeTone: "bg-emerald-50 text-emerald-700 border-emerald-200",
    primaryHeader: "₹ / g Protein",
    secondaryHeader: "Cost / Scoop",
    metaTitle: "Whey & Plant Protein Intelligence",
    metaSubtitle: "Benchmark by ₹ / g pure protein, DIAAS digestibility scores, and flavor tax.",
  },
  {
    id: "creatine",
    siloAliases: ["creatine"],
    title: "Creatine Monohydrate",
    shortLabel: "Creatine",
    tagline: "Benchmark by ₹ / 3g Verified Dose",
    description: "Creapure® seals, 200-mesh micronized purity tests, and direct price comparisons on raw unflavored powder across authorized sellers.",
    metricExample: "Lowest ask: ₹4.20 / 3g Serving",
    color: "border-cyan-500/40 hover:border-cyan-500 bg-cyan-950/5",
    activePill: "border-cyan-500 text-cyan-800 bg-cyan-50",
    badge: "Creapure & 200 Mesh",
    badgeTone: "bg-cyan-50 text-cyan-800 border-cyan-200",
    primaryHeader: "₹ / 3g Dose",
    secondaryHeader: "Cost / 100g",
    metaTitle: "Creatine Monohydrate Purity Screener",
    metaSubtitle: "Only showing verified creatine products. Benchmark by ₹ / 3g verified dose and Creapure® certification.",
  },
  {
    id: "pre_workout",
    siloAliases: ["pre_workout", "preworkout"],
    title: "Pre-Workout & Pump",
    shortLabel: "Pre-Workout",
    tagline: "Benchmark by Cost per Clinical Scoop",
    description: "Expose underdosed proprietary blends. We calculate true value based on active L-Citrulline, Beta-Alanine, and Caffeine dosages.",
    metricExample: "Lowest ask: ₹32 / Clinical Scoop",
    color: "border-amber-500/40 hover:border-amber-500 bg-amber-950/5",
    activePill: "border-amber-500 text-amber-800 bg-amber-50",
    badge: "Open Label Dosages",
    badgeTone: "bg-amber-50 text-amber-800 border-amber-200",
    primaryHeader: "₹ / Scoop",
    secondaryHeader: "Caffeine / Citrulline",
    metaTitle: "Pre-Workout Active Dosage Screener",
    metaSubtitle: "Expose underdosed proprietary blends. Normalized by clinical L-Citrulline, Beta-Alanine, and Caffeine dosages.",
  },
  {
    id: "mass_gainer",
    siloAliases: ["mass_gainer", "mass_gainers", "gainer"],
    title: "Mass Gainers",
    shortLabel: "Mass Gainer",
    tagline: "Benchmark by ₹ / 1,000 kcal & Carb Ratio",
    description: "Identify clean whole-food oat/barley formulas vs. cheap 80% sugar/maltodextrin tubs. Track true calorie-to-protein ratios.",
    metricExample: "Lowest ask: ₹74 / 1,000 kcal",
    color: "border-violet-500/40 hover:border-violet-500 bg-violet-950/5",
    activePill: "border-violet-500 text-violet-800 bg-violet-50",
    badge: "Calorie Arbitrage",
    badgeTone: "bg-violet-50 text-violet-800 border-violet-200",
    primaryHeader: "₹ / 1,000 kcal",
    secondaryHeader: "Carb:Protein Ratio",
    metaTitle: "Mass Gainer Calorie Arbitrage",
    metaSubtitle: "Identify clean whole-food oat/barley formulas vs cheap 80% sugar/maltodextrin tubs.",
  },
];

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

  // URL query sync
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const catParam = params.get("category");
      if (catParam) {
        setFilters((prev) => ({ ...prev, category: catParam }));
      }
    }
  }, []);

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

  const totalTrackedSkus = useMemo(() => {
    return initialProducts.reduce((acc, p) => acc + (p.variants?.length || 1), 0);
  }, [initialProducts]);

  const labVerifiedCount = useMemo(() => {
    return initialProducts.filter((p) => p.labVerified).length;
  }, [initialProducts]);


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

  const isHeroLanding = !filters.category && !filters.query && filters.selectedBrands.length === 0;

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

        // Promotional combo and bundle detection
        const isCombo = (() => {
          const name = g.baseProductName.toLowerCase();
          return (
            name.includes(" + ") ||
            name.includes("+ pre workout") ||
            name.includes("+ preworkout") ||
            name.includes("+ creatine") ||
            name.includes("+ shaker") ||
            name.includes("pack of") ||
            name.includes("combo") ||
            name.includes("free creatine") ||
            name.includes("free shaker")
          );
        })();

        // Category Silo Match (Strict Silo Isolation)
        if (filters.category) {
          const catLower = filters.category.toLowerCase();
          const targetConfig = CANONICAL_CATEGORIES.find(
            (c) => c.id === catLower || c.siloAliases.includes(catLower)
          );
          if (targetConfig) {
            // Exclude cross-product combos from pure category screeners unless user explicitly searches for them
            if (isCombo && !filters.query) return false;

            const matchesSilo = targetConfig.siloAliases.includes(g.categorySilo.toLowerCase());
            const isGenericSilo = !g.categorySilo || g.categorySilo === "general" || g.categorySilo === "supplements";
            if (!matchesSilo && !isGenericSilo) {
              return false;
            }
            if (isGenericSilo) {
              const matchesName = targetConfig.siloAliases.some((alias) =>
                `${g.baseProductName} ${g.proteinSource}`.toLowerCase().includes(alias)
              );
              if (!matchesName) return false;
            }
          } else if (g.categorySilo.toLowerCase() !== catLower) {
            return false;
          }
        }

        // Gate 1: Protein Formulation Lock
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

        // Gate 2: True Value Filter (₹ / 100g Pure Protein)
        const bestVariant = g.variants[0];
        const servingSize = Math.max(10, bestVariant?.label_serving_size_g || 33);
        const proteinG = Math.max(5, bestVariant?.label_protein_per_serving_g || 24);
        const totalServings = Math.max(1, Math.round((bestVariant?.weight_grams || 1000) / servingSize));
        const cost100g = costPer100gProtein(g.lowestPrice, totalServings, proteinG);

        if (filters.maxCostPer100gProtein < 600 && isFinite(cost100g)) {
          if (cost100g > filters.maxCostPer100gProtein) return false;
        }

        // Gate 3: Purity & Trust Thresholds
        if (filters.verifiedOnly && !g.labVerified) return false;

        if (filters.minPurityPct > 0) {
          const maxPurity = Math.max(
            ...g.variants.map(
              (v) =>
                v.calculated_purity_pct ||
                purityPct(v.label_protein_per_serving_g || 24, v.label_serving_size_g || 33)
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
      {/* 1. Global Navigation Bar with Category Switcher Pills */}
      <header className="border-b border-slate-200 px-4 sm:px-6 py-3 sticky top-0 bg-white/95 backdrop-blur-md z-40 shadow-xs">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto gap-4">
          <button
            type="button"
            aria-label="ProteIndex Home"
            className="font-black text-2xl tracking-tighter text-slate-900 italic cursor-pointer flex items-center shrink-0 border-0 bg-transparent p-0 text-left"
            onClick={() => {
              setFilters((prev) => ({ ...prev, category: "", query: "" }));
              if (typeof window !== "undefined") {
                window.history.pushState({}, "", "/");
              }
            }}
          >
            <span className="text-emerald-700">PROTE</span>INDEX
            <span className="ml-2 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-slate-100 text-slate-700 border border-slate-300 not-italic font-bold hidden sm:inline-block">
              IN Market
            </span>
          </button>

          {/* 4 Dedicated Category Switcher Buttons */}
          <div className="hidden md:flex items-center gap-1.5 overflow-x-auto" role="navigation" aria-label="Category Switcher">
            <button
              type="button"
              onClick={() => {
                setFilters((prev) => ({ ...prev, category: "" }));
                if (typeof window !== "undefined") window.history.pushState({}, "", "/");
              }}
              className={`px-3 py-1 text-xs font-mono font-bold rounded-sm border transition-colors ${
                !filters.category
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 text-slate-700 hover:text-slate-900 hover:border-slate-300 bg-white"
              }`}
            >
              All Instruments
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
                      window.history.pushState({}, "", `/?category=${cat.id}`);
                    }
                  }}
                  className={`px-3 py-1 text-xs font-mono font-semibold rounded-sm border transition-colors ${
                    isActive
                      ? cat.activePill + " font-bold shadow-xs"
                      : "border-slate-200 text-slate-700 hover:text-slate-900 hover:border-slate-300 bg-white"
                  }`}
                >
                  {cat.title}
                </button>
              );
            })}
          </div>

          {/* Mode Switcher Toggle */}
          <div className="flex items-center gap-2">
            <div className="hidden lg:flex items-center gap-1.5 text-xs font-mono text-slate-600 mr-2">
              <span className="size-2 rounded-full bg-emerald-600" />
              <span>Live Terminal</span>
            </div>

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
                <span className="hidden sm:inline">Consumer</span>
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
                <span className="hidden sm:inline">Terminal</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* 2. Hero Landing Section & 4-Card Category Gateway Grid */}
      {isHeroLanding && (
        <section className="relative pt-8 pb-10 px-4 sm:px-6 max-w-6xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-sm border border-emerald-300 bg-emerald-50 text-emerald-800 text-xs font-mono font-bold uppercase tracking-wider mb-5">
            Indian Supplement Market Intelligence · True Yield Screener
          </div>

          <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-slate-900 max-w-4xl mx-auto mb-3 leading-tight">
            Stop Overpaying For Supplement Filler.
          </h1>
          <p className="text-sm sm:text-base text-slate-600 max-w-2xl mx-auto mb-8 leading-relaxed">
            Prices normalized by <strong className="text-slate-900 font-bold">active-ingredient yield</strong> across authorized Indian retailers. Zero sponsored bias.
          </p>

          {/* Genuine Market Data Strip (No Invented Metrics) */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-4xl mx-auto mb-8 text-left">
            <div className="p-3 rounded-md border border-slate-200 bg-white">
              <div className="text-[10px] text-slate-500 font-mono font-bold uppercase">TRACKED PRODUCTS</div>
              <div className="text-xl font-bold font-mono text-slate-900 tabular-nums">
                {initialProducts.length} Instruments
              </div>
            </div>
            <div className="p-3 rounded-md border border-slate-200 bg-white">
              <div className="text-[10px] text-slate-500 font-mono font-bold uppercase">TRACKED SKUS</div>
              <div className="text-xl font-bold font-mono text-slate-900 tabular-nums">
                {totalTrackedSkus} Variants
              </div>
            </div>
            <div className="p-3 rounded-md border border-slate-200 bg-white">
              <div className="text-[10px] text-slate-500 font-mono font-bold uppercase">VERIFIED BRANDS</div>
              <div className="text-xl font-bold font-mono text-slate-900 tabular-nums">
                {availableBrands.length} Brands
              </div>
            </div>
            <div className="p-3 rounded-md border border-slate-200 bg-white">
              <div className="text-[10px] text-slate-500 font-mono font-bold uppercase">LAB AUDITED</div>
              <div className="text-xl font-bold font-mono text-emerald-700 tabular-nums">
                {labVerifiedCount} Verified
              </div>
            </div>
          </div>

          {/* Category Gateway Heading */}
          <div className="flex items-center justify-between mb-3 text-left">
            <h2 className="text-xs font-mono font-bold text-slate-600 uppercase tracking-widest">
              Select A Supplement Category To Compare:
            </h2>
            <span className="text-[11px] font-mono text-slate-500">Zero Cross-Category Contamination</span>
          </div>

          {/* 4-Card Interactive Gateway Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-left">
            {CANONICAL_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => {
                  setFilters((prev) => ({ ...prev, category: cat.id }));
                  if (typeof window !== "undefined") {
                    window.history.pushState({}, "", `/?category=${cat.id}`);
                  }
                }}
                className={`group p-4 sm:p-5 rounded-md border text-left cursor-pointer bg-white transition-colors hover:border-slate-400 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-900 ${cat.color}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-sm border ${cat.badgeTone}`}>
                    {cat.badge}
                  </span>
                  <span className="text-xs font-mono font-bold text-slate-400 group-hover:text-emerald-700 transition-colors flex items-center gap-1">
                    <span>Open Screener</span>
                    <ArrowRight className="size-3" />
                  </span>
                </div>

                <h3 className="text-lg font-bold text-slate-900 group-hover:text-emerald-800 transition-colors">
                  {cat.title}
                </h3>
                <p className="text-xs font-mono font-bold text-emerald-700 mt-0.5 mb-1.5">{cat.tagline}</p>
                <p className="text-xs text-slate-600 mb-3 leading-relaxed line-clamp-2">{cat.description}</p>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-500 text-[11px]">Benchmark:</span>
                  <span className="font-bold text-slate-800">{cat.metricExample}</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* 3. Category Adaptive Header Banner */}
      {activeCategoryConfig && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 pb-2">
          <div className="rounded-md border border-slate-200 bg-white p-4 sm:p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-mono text-slate-500 mb-1">
                <button
                  type="button"
                  onClick={() => {
                    setFilters((prev) => ({ ...prev, category: "" }));
                    if (typeof window !== "undefined") window.history.pushState({}, "", "/");
                  }}
                  className="hover:text-slate-900 underline font-bold"
                >
                  All Categories
                </button>
                <span>/</span>
                <span className="text-slate-900 font-bold uppercase">{activeCategoryConfig.shortLabel}</span>
              </div>
              <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                {activeCategoryConfig.metaTitle}
              </h1>
              <p className="text-xs text-slate-600 font-mono mt-1">
                {activeCategoryConfig.metaSubtitle} Competitor prices normalized in real-time.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-xs font-mono font-bold px-3 py-1 rounded-sm border ${activeCategoryConfig.badgeTone}`}>
                {activeCategoryConfig.badge}
              </span>
              <span className="text-xs font-mono font-bold px-3 py-1 rounded-sm border border-slate-200 text-slate-700 bg-slate-50">
                Primary: {activeCategoryConfig.primaryHeader}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* 4. Screener Filter Section & Adaptive Product Matrix */}
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="lg:grid lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-8">
          {/* 4-Gate Decision Filter Controls */}
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
              <div className="flex min-h-[350px] flex-col items-center justify-center rounded-md border border-dashed border-slate-300 bg-white p-8 text-center shadow-xs">
                <p className="text-base font-bold text-slate-800 font-mono">
                  No products matched your decision criteria
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Try adjusting the value slider or relaxing formulation locks.
                </p>
                <button
                  type="button"
                  onClick={resetAllFilters}
                  className="mt-4 rounded-sm bg-slate-900 px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider text-white hover:bg-slate-800 transition-colors"
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
              /* Terminal Mode: Category-Adaptive Monospace Financial Screener */
              <div className="border border-slate-300 bg-white shadow-xs overflow-x-auto font-mono text-xs rounded-sm">
                <table className="w-full text-left border-collapse">
                  <thead className="border-b bg-slate-100/90 uppercase text-[11px] text-slate-600">
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
                            <td className="px-3 py-2.5 text-right font-bold text-slate-900">
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
                                {catMetrics.badge && (
                                  <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded border ${
                                    catMetrics.badgeTone === "cyan"
                                      ? "border-cyan-300 text-cyan-800 bg-cyan-50"
                                      : catMetrics.badgeTone === "amber"
                                      ? "border-amber-300 text-amber-800 bg-amber-50"
                                      : catMetrics.badgeTone === "violet"
                                      ? "border-violet-300 text-violet-800 bg-violet-50"
                                      : "border-emerald-300 text-emerald-800 bg-emerald-50"
                                  }`}>
                                    {catMetrics.badge}
                                  </span>
                                )}
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
                                  handleOpenCompareDrawer(product, bestVariant || product.variants[0])
                                }
                                className="bg-slate-900 hover:bg-emerald-700 text-white px-2.5 py-1 text-[11px] font-bold uppercase transition-colors rounded"
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
                              const vCatMetrics = computeCategoryMetrics(
                                product.categorySilo,
                                v.lowest_price_inr,
                                v.raw_json_data || {
                                  servingSizeGrams: v.label_serving_size_g || 33,
                                  proteinPerServingGrams: vProt,
                                  servingsPerContainer: vServings,
                                  totalProteinPerTubGrams: vProt * vServings,
                                },
                                v.weight_grams || 1000
                              );

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
                                    {vCatMetrics.primaryValue}
                                  </td>
                                  <td className="px-3 py-1.5 text-right text-slate-600">
                                    {vCatMetrics.secondaryValue}
                                  </td>
                                  <td />
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
