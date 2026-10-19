"use client";

import React, { useState, useMemo } from "react";
import { Scale, ShieldCheck, AlertCircle, ArrowUpRight, Check, Clock } from "lucide-react";
import { GroupedProduct, DbVariant } from "../ProductBrowser";
import { formatInr, computeCategoryMetrics, indexedAgo } from "@/lib/analytics";

interface SneakopediaCardProps {
  product: GroupedProduct;
  onOpenMatrix: (product: GroupedProduct, variant: DbVariant) => void;
  onToggleCompareTray?: (variant: DbVariant, group: GroupedProduct) => void;
  isTraySelected?: boolean;
}

export const SneakopediaCard: React.FC<SneakopediaCardProps> = ({
  product,
  onOpenMatrix,
  onToggleCompareTray,
  isTraySelected = false,
}) => {
  const variants = product.variants || [];

  // Extract distinct weights
  const availableWeights = useMemo(() => {
    const set = new Set<number>();
    variants.forEach((v) => {
      if (v.weight_grams > 0) set.add(v.weight_grams);
    });
    return Array.from(set).sort((a, b) => a - b);
  }, [variants]);

  // Selected weight state machine
  const [selectedWeight, setSelectedWeight] = useState<number>(() => {
    if (availableWeights.includes(1000)) return 1000;
    return availableWeights[0] || 1000;
  });

  // Active variant resolution
  const activeVariant = useMemo<DbVariant>(() => {
    const exact = variants.find((v) => v.weight_grams === selectedWeight);
    if (exact) return exact;
    return variants[0] || {
      id: `${product.id}-default`,
      sku_id: `${product.id}-default`,
      flavor: "Standard",
      weight_grams: selectedWeight,
      lowest_price_inr: product.lowestPrice,
      best_value_metric: product.bestValueMetric,
      label_protein_per_serving_g: null,
      label_serving_size_g: null,
      calculated_purity_pct: null,
      raw_json_data: null,
      price_listings: [],
    };
  }, [variants, selectedWeight, product]);

  const currentPrice = activeVariant.lowest_price_inr || product.lowestPrice || 0;
  
  // Real values without corrupt 24/33 fallbacks
  const rawServingSize = activeVariant.label_serving_size_g ?? null;
  const rawProteinG = activeVariant.label_protein_per_serving_g ?? null;
  const hasValidProtein = rawProteinG !== null && rawServingSize !== null && rawServingSize > 0 && rawProteinG > 0 && rawProteinG <= rawServingSize;

  const servingSize = hasValidProtein ? rawServingSize! : 0;
  const proteinG = hasValidProtein ? rawProteinG! : 0;
  const totalServings = hasValidProtein && servingSize > 0 ? Math.max(1, Math.round(activeVariant.weight_grams / servingSize)) : 0;

  const catMetrics = useMemo(() => {
    return computeCategoryMetrics(
      product.categorySilo,
      currentPrice,
      activeVariant.raw_json_data || (hasValidProtein ? {
        servingSizeGrams: servingSize,
        proteinPerServingGrams: proteinG,
        servingsPerContainer: totalServings,
        totalProteinPerTubGrams: proteinG * totalServings,
      } : {}),
      activeVariant.weight_grams
    );
  }, [product.categorySilo, currentPrice, activeVariant, hasValidProtein, servingSize, proteinG, totalServings]);

  const listings = activeVariant.price_listings || [];
  const storeCount = Math.max(1, listings.length || product.sellerCount || 1);
  const inStockOffers = listings.filter((l) => l.in_stock !== false && l.is_in_stock !== false);
  const isInStock = listings.length === 0 ? true : inStockOffers.length > 0;

  // Real freshness timestamp from listing data or fallback
  const freshestScrapedAt = useMemo(() => {
    for (const l of listings) {
      if (l.scraped_at) return l.scraped_at;
    }
    return activeVariant.last_observed_at || product.lastObservedAt;
  }, [listings, activeVariant, product]);

  const freshnessLabel = freshestScrapedAt ? indexedAgo(freshestScrapedAt) : "Recently";

  // Category normalization for UI labels
  const isCreatine = product.categorySilo?.toLowerCase().includes("creatine");
  const isGainer = product.categorySilo?.toLowerCase().includes("gainer");

  return (
    <article className="group flex flex-col justify-between bg-white border border-slate-200 rounded-sm hover:border-slate-400 transition-colors overflow-hidden h-[438px] max-w-full">
      <div className="flex flex-col">
        {/* Top Image Frame with Trust Signals & Direct Compare Trigger */}
        <div className="relative h-44 w-full bg-slate-50 flex items-center justify-center p-4 border-b border-slate-100 shrink-0">
          {/* Trust Badges */}
          <div className="absolute left-2.5 top-2.5 z-10 flex flex-col gap-1 items-start">
            {product.labVerified ? (
              <span className="inline-flex items-center gap-1 rounded-xs bg-emerald-700 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-xs">
                <ShieldCheck className="size-3" /> Lab Verified
              </span>
            ) : null}
            {product.aminoSpikeRisk ? (
              <span className="inline-flex items-center gap-1 rounded-xs bg-rose-700 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-xs">
                <AlertCircle className="size-3" /> Amino Spiked
              </span>
            ) : product.isFairyDusted ? (
              <span className="inline-flex items-center gap-1 rounded-xs bg-amber-600 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-xs">
                <AlertCircle className="size-3" /> Filler Warning
              </span>
            ) : null}
            {!product.labVerified && !product.isFairyDusted && !product.aminoSpikeRisk && (
              <span className="inline-flex items-center gap-1 rounded-xs bg-slate-200/90 text-slate-700 px-1.5 py-0.5 text-[9px] font-mono font-semibold uppercase">
                {product.proteinSource || product.categorySilo.replace(/_/g, " ")}
              </span>
            )}
          </div>

          {/* Direct Compare Tray Toggle */}
          {onToggleCompareTray && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleCompareTray(activeVariant, product);
              }}
              className={`absolute right-2.5 top-2.5 z-10 flex items-center gap-1 px-2 py-1 rounded-xs border text-[10px] font-mono font-bold transition-all ${
                isTraySelected
                  ? "bg-emerald-700 border-emerald-700 text-white shadow-xs"
                  : "bg-white/95 border-slate-200 text-slate-700 hover:border-slate-900 hover:text-slate-900 shadow-xs"
              }`}
              title="Add to Cross-Product Comparison"
              aria-label={`Compare ${product.baseProductName}`}
            >
              <Scale className="size-3" />
              <span>{isTraySelected ? "Comparing" : "Compare"}</span>
            </button>
          )}

          {/* Product Image */}
          {product.imageUrl ? (
            <img
              src={product.imageUrl}
              alt={product.baseProductName}
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLElement).style.display = "none";
              }}
              className="h-full w-full object-contain mix-blend-multiply"
            />
          ) : (
            <div className="text-xs text-slate-400 font-mono font-medium">No Image Available</div>
          )}
        </div>

        {/* Product Identity & Primary Metric Anchor */}
        <div className="p-3.5 flex flex-col gap-1.5">
          {/* Brand & Silo Header */}
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
            <span className="text-slate-700 font-black">{product.brand}</span>
            <span className="text-slate-400">{product.categorySilo.replace(/_/g, " ")}</span>
          </div>

          {/* Clamped 2-line Title */}
          <h3
            title={product.baseProductName}
            className="line-clamp-2 text-xs sm:text-sm font-bold text-slate-900 leading-snug h-9"
          >
            {product.baseProductName}
          </h3>

          {/* Primary Equalized Metric Anchor (₹/g Protein Dominant) */}
          <div className="flex items-baseline justify-between gap-1 pt-0.5">
            <div className="flex items-baseline gap-1.5">
              {catMetrics.isPending ? (
                <span className="text-xs font-mono font-bold text-amber-800 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded-xs">
                  Pending Verification
                </span>
              ) : (
                <>
                  <span className="text-lg font-mono font-black text-emerald-800 tabular-nums tracking-tight">
                    {catMetrics.primaryValue}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500 font-semibold">
                    {catMetrics.primaryLabel}
                  </span>
                </>
              )}
            </div>

            {/* Benchmark pill */}
            {!catMetrics.isPending && (
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-xs border border-slate-200 bg-slate-50 text-slate-700">
                {catMetrics.secondaryValue} {catMetrics.secondaryLabel}
              </span>
            )}
          </div>

          {/* Weight Variant Switcher */}
          {availableWeights.length > 1 ? (
            <div className="flex flex-wrap gap-1 mt-0.5">
              {availableWeights.map((w) => {
                const isSelected = selectedWeight === w;
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setSelectedWeight(w)}
                    className={`px-1.5 py-0.5 text-[9px] font-mono font-bold rounded-xs transition-colors ${
                      isSelected
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {w >= 1000 ? `${w / 1000}kg` : `${w}g`}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="text-[10px] font-mono text-slate-400 mt-0.5">
              Standard Pack: {selectedWeight >= 1000 ? `${selectedWeight / 1000}kg` : `${selectedWeight}g`}
            </div>
          )}

          {/* Quantitative Nutrition / Purity Data State */}
          <div className="text-[10px] font-mono text-slate-600 bg-slate-50 border border-slate-200/80 px-2 py-1.5 rounded-xs flex items-center justify-between mt-0.5">
            {isCreatine ? (
              <>
                <span>Creatine Monohydrate</span>
                <span className="font-bold text-cyan-800 bg-cyan-50 px-1.5 py-0.5 rounded-xs border border-cyan-200">100% Purity</span>
              </>
            ) : isGainer ? (
              <>
                <span>Calorie & Carb Formula</span>
                <span className="font-bold text-violet-800 bg-violet-50 px-1.5 py-0.5 rounded-xs border border-violet-200">{catMetrics.secondaryValue}</span>
              </>
            ) : hasValidProtein ? (
              <>
                <span>{proteinG}g Prot / {servingSize}g scoop</span>
                {(() => {
                  const pct = Math.round((proteinG / servingSize) * 100);
                  const tone = pct >= 75
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : pct >= 60
                    ? "bg-amber-50 text-amber-800 border-amber-200"
                    : "bg-rose-50 text-rose-800 border-rose-200";
                  return (
                    <span className={`font-bold px-1.5 py-0.5 rounded-xs border ${tone}`}>
                      {pct}% Purity
                    </span>
                  );
                })()}
              </>
            ) : (
              <span className="text-slate-400 italic">Nutrition label pending audit</span>
            )}
          </div>

          {/* Pricing, Seller Freshness & Stock Metadata */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs font-mono">
            <div>
              <span className="text-[9px] text-slate-400 uppercase tracking-wider block">Best Price</span>
              <span className="text-base font-black text-slate-900 tabular-nums">
                {formatInr(currentPrice)}
              </span>
            </div>

            <div className="flex flex-col items-end text-[10px]">
              <div className="flex items-center gap-1.5 font-semibold">
                <span className={`inline-block size-1.5 rounded-full ${isInStock ? "bg-emerald-600" : "bg-red-500"}`} />
                <span className={isInStock ? "text-slate-700" : "text-red-600 font-bold"}>
                  {isInStock ? `${storeCount} ${storeCount === 1 ? "seller" : "sellers"}` : "Out of stock"}
                </span>
              </div>
              <div className="flex items-center gap-1 text-[9px] text-slate-400 mt-0.5">
                <Clock className="size-2.5" />
                <span>{freshnessLabel}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Footer: View Best Price & Full History */}
      <div className="p-3.5 pt-0">
        <button
          type="button"
          onClick={() => onOpenMatrix(product, activeVariant)}
          className="w-full flex items-center justify-center gap-1.5 py-2 px-3 bg-slate-900 hover:bg-emerald-800 text-white text-xs font-mono font-bold uppercase tracking-wider rounded-sm transition-colors cursor-pointer"
        >
          <span>Compare {storeCount} {storeCount === 1 ? "Store" : "Stores"}</span>
          <ArrowUpRight className="size-3.5 text-slate-400" />
        </button>
      </div>
    </article>
  );
};
