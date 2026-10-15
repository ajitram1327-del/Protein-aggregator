"use client";

import React, { useState, useMemo } from "react";
import { Scale, ShieldCheck, AlertCircle, ArrowUpRight } from "lucide-react";
import { GroupedProduct, DbVariant } from "../ProductBrowser";
import { formatInr, computeCategoryMetrics } from "@/lib/analytics";

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
      label_protein_per_serving_g: 24,
      label_serving_size_g: 33,
      raw_json_data: null,
      price_listings: [],
    };
  }, [variants, selectedWeight, product]);

  const currentPrice = activeVariant.lowest_price_inr || product.lowestPrice || 0;
  const servingSize = Math.max(10, activeVariant.label_serving_size_g || 33);
  const proteinG = Math.max(5, activeVariant.label_protein_per_serving_g || 24);
  const totalServings = Math.max(1, Math.round(activeVariant.weight_grams / servingSize));

  const catMetrics = useMemo(() => {
    return computeCategoryMetrics(
      product.categorySilo,
      currentPrice,
      activeVariant.raw_json_data || {
        servingSizeGrams: servingSize,
        proteinPerServingGrams: proteinG,
        servingsPerContainer: totalServings,
        totalProteinPerTubGrams: proteinG * totalServings,
        diaasScore: 1.15,
      },
      activeVariant.weight_grams
    );
  }, [product.categorySilo, currentPrice, activeVariant, servingSize, proteinG, totalServings]);

  const storeCount = Math.max(1, activeVariant.price_listings?.length || 4);

  return (
    <article className="group flex flex-col justify-between bg-white border border-slate-200 rounded-sm hover:border-slate-400 transition-colors overflow-hidden">
      <div>
        {/* Clean Image Frame (Inspired by Sneakopedia drops) */}
        <div className="relative aspect-square w-full bg-slate-50 flex items-center justify-center p-5 border-b border-slate-100">
          {/* Trust Badges */}
          <div className="absolute left-2.5 top-2.5 z-10 flex flex-col gap-1 items-start">
            {product.labVerified && (
              <span className="inline-flex items-center gap-1 rounded-xs bg-emerald-700 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-xs">
                <ShieldCheck className="size-3" /> Lab Verified
              </span>
            )}
            {product.isFairyDusted && (
              <span className="inline-flex items-center gap-1 rounded-xs bg-amber-600 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-xs">
                <AlertCircle className="size-3" /> Filler Warning
              </span>
            )}
          </div>

          {/* Compare tray icon */}
          {onToggleCompareTray && (
            <button
              type="button"
              onClick={() => onToggleCompareTray(activeVariant, product)}
              className={`absolute right-2.5 top-2.5 z-10 p-1.5 rounded-xs border text-xs font-mono transition-colors ${
                isTraySelected
                  ? "bg-emerald-700 border-emerald-700 text-white"
                  : "bg-white/95 border-slate-200 text-slate-600 hover:bg-white hover:text-slate-900"
              }`}
              title="Add to Cross-Product Matrix"
            >
              <Scale className="size-3.5" />
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
            <div className="text-xs text-slate-400 font-mono font-medium">No Image</div>
          )}
        </div>

        {/* Product Meta */}
        <div className="p-3.5 sm:p-4">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold mb-1">
            <span>{product.brand}</span>
            <span>{product.proteinSource || product.categorySilo.replace(/_/g, " ")}</span>
          </div>

          <h3
            title={product.baseProductName}
            className="line-clamp-2 text-sm font-bold text-slate-900 leading-snug h-[40px]"
          >
            {product.baseProductName}
          </h3>

          {/* In-Card Weight Switcher */}
          {availableWeights.length > 1 && (
            <div className="mt-2.5 flex flex-wrap gap-1">
              {availableWeights.map((w) => {
                const isSelected = selectedWeight === w;
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setSelectedWeight(w)}
                    className={`px-2 py-0.5 text-[10px] font-mono font-semibold rounded-xs transition-colors ${
                      isSelected
                        ? "bg-slate-900 text-white font-bold"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {w >= 1000 ? `${w / 1000}kg` : `${w}g`}
                  </button>
                );
              })}
            </div>
          )}

          {/* Pricing & Sneakopedia Green Headline */}
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-baseline justify-between gap-1">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase block">Starting from</span>
              <span className="text-lg font-mono tabular-nums font-black text-emerald-700">
                {formatInr(currentPrice)}
              </span>
            </div>

            <div className="text-right">
              <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-xs border border-emerald-300 bg-emerald-50 text-emerald-800">
                {catMetrics.primaryValue} {catMetrics.primaryLabel}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Action Footer: Sneakopedia Open Matrix Button */}
      <div className="p-3.5 sm:p-4 pt-0">
        <button
          type="button"
          onClick={() => onOpenMatrix(product, activeVariant)}
          className="w-full flex items-center justify-center gap-1.5 py-2 px-3 bg-slate-900 hover:bg-emerald-800 text-white text-xs font-mono font-bold uppercase tracking-wider rounded-sm transition-colors"
        >
          <span>Compare {storeCount} Stores & History</span>
          <ArrowUpRight className="size-3.5 text-slate-400" />
        </button>
      </div>
    </article>
  );
};
