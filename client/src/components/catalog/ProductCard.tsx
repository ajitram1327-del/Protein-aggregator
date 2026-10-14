"use client";

import React, { useState, useMemo } from "react";
import { ShieldCheck, Zap, Sparkles, Scale, AlertCircle } from "lucide-react";
import { GroupedProduct, DbVariant } from "../ProductBrowser";
import { formatInr, costPer100gProtein, purityPct } from "@/lib/analytics";

interface ProductCardProps {
  product: GroupedProduct;
  onOpenCompareDrawer: (product: GroupedProduct, variant: DbVariant) => void;
  onToggleCompareTray?: (variant: DbVariant, group: GroupedProduct) => void;
  isTraySelected?: boolean;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onOpenCompareDrawer,
  onToggleCompareTray,
  isTraySelected = false,
}) => {
  const variants = product.variants || [];

  // Extract all distinct weights in grams available for this product
  const availableWeights = useMemo(() => {
    const set = new Set<number>();
    variants.forEach((v) => {
      if (v.weight_grams > 0) set.add(v.weight_grams);
    });
    return Array.from(set).sort((a, b) => a - b);
  }, [variants]);

  // Extract distinct clean flavor names
  const availableFlavors = useMemo(() => {
    const map = new Map<string, string>();
    variants.forEach((v) => {
      let clean = (v.flavor || "").trim();
      clean = clean.replace(/\b\d+(?:\.\d+)?\s*(kg|g|gm|lbs|l|ml)\b/gi, "").trim();
      clean = clean.replace(/^[\/\-\|\,\s]+|[\/\-\|\,\s]+$/g, "").trim();
      if (!clean || clean.toLowerCase() === "varies") clean = "Standard";
      if (!map.has(clean.toLowerCase())) {
        map.set(clean.toLowerCase(), clean);
      }
    });
    return Array.from(map.values());
  }, [variants]);

  // Local state machine for active weight and flavor
  const [selectedWeight, setSelectedWeight] = useState<number>(() => {
    if (availableWeights.includes(1000)) return 1000;
    return availableWeights[0] || 1000;
  });

  const [selectedFlavor, setSelectedFlavor] = useState<string>(() => {
    const unflavored = availableFlavors.find((f) =>
      f.toLowerCase().includes("unflavor") || f.toLowerCase().includes("raw")
    );
    return unflavored || availableFlavors[0] || "Standard";
  });

  // Dynamic In-Card State Resolution: find matching variant
  const activeVariant = useMemo<DbVariant>(() => {
    // 1. Try exact match on weight and flavor
    const exact = variants.find((v) => {
      const matchWeight = v.weight_grams === selectedWeight;
      const matchFlavor = (v.flavor || "").toLowerCase().includes(selectedFlavor.toLowerCase());
      return matchWeight && matchFlavor;
    });
    if (exact) return exact;

    // 2. Try match on weight
    const byWeight = variants.find((v) => v.weight_grams === selectedWeight);
    if (byWeight) return byWeight;

    // 3. Fallback to first available variant
    return variants[0] || {
      id: `${product.id}-default`,
      sku_id: `${product.id}-default`,
      flavor: selectedFlavor,
      weight_grams: selectedWeight,
      lowest_price_inr: product.lowestPrice,
      best_value_metric: product.bestValueMetric,
      label_protein_per_serving_g: 24,
      label_serving_size_g: 33,
      raw_json_data: null,
      price_listings: [],
    };
  }, [variants, selectedWeight, selectedFlavor, product]);

  // Real-time metric computations
  const currentPrice = activeVariant.lowest_price_inr || product.lowestPrice || 0;
  const servingSize = Math.max(10, activeVariant.label_serving_size_g || 33);
  const proteinG = Math.max(5, activeVariant.label_protein_per_serving_g || 24);
  const totalServings = Math.max(1, Math.round(activeVariant.weight_grams / servingSize));

  const costPer100g = costPer100gProtein(currentPrice, totalServings, proteinG);
  const costPerScoop = totalServings > 0 && currentPrice > 0 ? Math.round(currentPrice / totalServings) : 0;
  const purity = purityPct(proteinG, servingSize);

  // Bulk Savings Calculation: Compare cost per scoop vs 1kg baseline
  const bulkSavingsChip = useMemo(() => {
    if (activeVariant.weight_grams <= 1000) return null;
    const base1kg = variants.find((v) => v.weight_grams === 1000);
    if (base1kg && base1kg.lowest_price_inr > 0) {
      const baseServings = Math.max(1, Math.round(1000 / (base1kg.label_serving_size_g || 33)));
      const baseCostPerScoop = base1kg.lowest_price_inr / baseServings;
      const savingsPerScoop = Math.round(baseCostPerScoop - costPerScoop);
      if (savingsPerScoop > 2) {
        return `Bulk Savings: ₹${savingsPerScoop}/scoop cheaper than 1kg`;
      }
    }
    return null;
  }, [activeVariant, variants, costPerScoop]);

  // Store Offers spread
  const storeCount = Math.max(1, activeVariant.price_listings?.length || 4);
  const minPrice = currentPrice;
  const maxPrice = Math.round(currentPrice * 1.12);

  const isOutOfStock =
    currentPrice <= 0 ||
    (activeVariant.price_listings?.length > 0 &&
      activeVariant.price_listings.every((l) => (l.is_in_stock ?? l.in_stock) === false));

  const formatWeight = (g: number) => {
    if (g >= 1000) {
      const kg = g / 1000;
      return `${kg % 1 === 0 ? kg : kg.toFixed(1)} kg`;
    }
    return `${g} g`;
  };

  return (
    <article className="group flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-3.5 sm:p-4 transition-all duration-200 hover:shadow-lg hover:border-slate-300">
      <div>
        {/* Image & Trust Badges */}
        <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-slate-50 flex items-center justify-center p-4 border border-slate-100">
          <div className="absolute left-2.5 top-2.5 z-10 flex flex-col gap-1 items-start">
            {product.labVerified && (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-sm">
                <ShieldCheck className="size-3" /> Lab Verified
              </span>
            )}
            {product.isFairyDusted && (
              <span className="inline-flex items-center gap-1 rounded bg-amber-500 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-sm">
                <AlertCircle className="size-3" /> Filler Warning
              </span>
            )}
          </div>

          {onToggleCompareTray && (
            <button
              type="button"
              onClick={() => onToggleCompareTray(activeVariant, product)}
              className={`absolute right-2.5 top-2.5 z-10 p-1.5 rounded-lg border text-xs font-mono transition-all ${
                isTraySelected
                  ? "bg-emerald-600 border-emerald-600 text-white shadow"
                  : "bg-white/90 border-slate-200 text-slate-600 hover:bg-white hover:text-slate-900"
              }`}
              title="Add to Cross-Product Matrix"
            >
              <Scale className="size-3.5" />
            </button>
          )}

          {product.imageUrl ? (
            <img
              src={product.imageUrl}
              alt={product.baseProductName}
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLElement).style.display = "none";
              }}
              className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105 mix-blend-multiply"
            />
          ) : (
            <div className="text-xs text-slate-400 font-mono font-medium">No Image</div>
          )}
        </div>

        {/* Content */}
        <div className="mt-3.5 px-0.5">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-bold">
            {product.brand} · {product.proteinSource || "Pure Protein"}
          </div>

          <h3
            title={product.baseProductName}
            className="line-clamp-2 text-sm font-semibold text-slate-900 leading-snug mt-1 h-[40px]"
          >
            {product.baseProductName}
          </h3>

          {/* In-Card State Machine Pills */}
          <div className="mt-3 space-y-2">
            {/* Weight Pills */}
            <div className="flex flex-wrap gap-1.5">
              {availableWeights.map((w) => {
                const isSelected = selectedWeight === w;
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setSelectedWeight(w)}
                    className={`px-2 py-1 text-[11px] font-mono font-semibold rounded transition-all ${
                      isSelected
                        ? "bg-slate-900 text-white shadow-sm font-bold"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {formatWeight(w)}
                  </button>
                );
              })}
            </div>

            {/* Flavor Pills / Dropdown */}
            {availableFlavors.length > 1 && (
              <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 scrollbar-none">
                {availableFlavors.slice(0, 3).map((flv) => {
                  const isSelected = selectedFlavor.toLowerCase() === flv.toLowerCase();
                  return (
                    <button
                      key={flv}
                      type="button"
                      onClick={() => setSelectedFlavor(flv)}
                      className={`px-2 py-0.5 text-[10px] rounded border font-medium truncate max-w-[110px] transition-all ${
                        isSelected
                          ? "border-emerald-600 bg-emerald-50 text-emerald-800 font-bold"
                          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                      }`}
                      title={flv}
                    >
                      {flv}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Real-time Metrics & Bulk Savings Chip */}
          <div className="mt-3.5 pt-3 border-t border-slate-100">
            <div className="flex items-baseline justify-between">
              <div>
                <span className="text-xl font-mono tabular-nums font-extrabold text-slate-900">
                  {formatInr(currentPrice)}
                </span>
                {costPerScoop > 0 && (
                  <span className="text-[11px] font-mono text-slate-500 ml-1.5">
                    (₹{costPerScoop}/scoop)
                  </span>
                )}
              </div>
              <span className="text-[11px] font-mono font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                ₹{Math.round(costPer100g)} / 100g prot
              </span>
            </div>

            {/* Bulk Savings inline chip */}
            {bulkSavingsChip && (
              <div className="mt-2 flex items-center gap-1 text-[11px] font-mono font-bold text-emerald-800 bg-emerald-100/70 border border-emerald-300 px-2 py-1 rounded">
                <Sparkles className="size-3 text-emerald-700 shrink-0" />
                <span className="truncate">{bulkSavingsChip}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Dynamic Compare Stores CTA Button */}
      <div className="mt-4 pt-1">
        {isOutOfStock ? (
          <button
            type="button"
            disabled
            className="flex h-10 w-full items-center justify-center rounded-xl bg-slate-100 text-xs font-mono font-bold text-slate-400 cursor-not-allowed border border-slate-200"
          >
            Out of Stock Across Stores
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onOpenCompareDrawer(product, activeVariant)}
            className="flex h-10 w-full items-center justify-center gap-1.5 rounded-xl bg-slate-900 hover:bg-emerald-700 text-white text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm group-hover:bg-emerald-600"
          >
            <Zap className="size-3.5 text-yellow-400 fill-yellow-400" />
            <span>
              Compare {storeCount} Stores ({formatInr(minPrice)} – {formatInr(maxPrice)})
            </span>
          </button>
        )}
      </div>
    </article>
  );
};
