"use client";

import React, { useState, useMemo, useEffect, useRef } from "react";
import { ShieldCheck, Zap, Sparkles, Scale, AlertCircle, ChevronDown, ExternalLink, Check } from "lucide-react";
import { GroupedProduct, DbVariant } from "../ProductBrowser";
import { formatInr } from "@/lib/analytics";
import {
  toParentProduct,
  resolveCardMetrics,
  cleanFlavorName,
  isUnflavoredFlavor,
  formatWeightDisplay,
  ResolvedSKUMetrics,
} from "@/lib/parentChildMatrix";

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
  // Convert GroupedProduct to typed ParentProduct model
  const parent = useMemo(() => toParentProduct(product), [product]);
  const variants = parent.variants;

  // 1. Extract all distinct weights manufactured across this parent product
  const availableWeights = useMemo(() => {
    const set = new Set<number>();
    variants.forEach((v) => {
      if (v.weightGrams > 0) set.add(v.weightGrams);
    });
    return Array.from(set).sort((a, b) => a - b);
  }, [variants]);

  // 2. Extract distinct clean flavor names across all variants
  const allProductFlavors = useMemo(() => {
    const list: string[] = [];
    const seen = new Set<string>();
    // Prioritize unflavored first
    variants.forEach((v) => {
      if (v.isUnflavored && !seen.has(v.flavor.toLowerCase())) {
        seen.add(v.flavor.toLowerCase());
        list.push(v.flavor);
      }
    });
    // Add other flavors
    variants.forEach((v) => {
      const lower = v.flavor.toLowerCase();
      if (!seen.has(lower)) {
        seen.add(lower);
        list.push(v.flavor);
      }
    });
    return list;
  }, [variants]);

  // 3. Reactive State Machine for active Weight and Flavor
  const [selectedWeight, setSelectedWeight] = useState<number>(() => {
    if (availableWeights.includes(1000)) return 1000;
    if (availableWeights.includes(2000)) return 2000;
    return availableWeights[0] || 1000;
  });

  const [selectedFlavor, setSelectedFlavor] = useState<string>(() => {
    const unflavored = allProductFlavors.find((f) => isUnflavoredFlavor(f));
    return unflavored || allProductFlavors[0] || "Standard";
  });

  const [isFlavorPopoverOpen, setIsFlavorPopoverOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsFlavorPopoverOpen(false);
      }
    };
    if (isFlavorPopoverOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isFlavorPopoverOpen]);

  // 4. Query Matrix: Determine available and in-stock flavors for currently active weight
  const weightVariants = useMemo(() => {
    return variants.filter((v) => v.weightGrams === selectedWeight);
  }, [variants, selectedWeight]);

  const flavorAvailabilityMap = useMemo(() => {
    const map = new Map<string, { isManufactured: boolean; inStock: boolean; price: number }>();
    allProductFlavors.forEach((flavor) => {
      const match = weightVariants.find(
        (v) => v.flavor.toLowerCase() === flavor.toLowerCase()
      );
      if (!match) {
        map.set(flavor.toLowerCase(), { isManufactured: false, inStock: false, price: 0 });
      } else {
        const availableListing = match.listings.find((l) => l.inStock && l.currentPrice > 0);
        const inStock = !!availableListing;
        const price = availableListing?.currentPrice || match.listings[0]?.currentPrice || 0;
        map.set(flavor.toLowerCase(), { isManufactured: true, inStock, price });
      }
    });
    return map;
  }, [allProductFlavors, weightVariants]);

  // 5. Reactive Transition: If active flavor is not manufactured in the new weight, auto-fallback
  const handleWeightChange = (newWeight: number) => {
    setSelectedWeight(newWeight);
    const variantsInNewWeight = variants.filter((v) => v.weightGrams === newWeight);
    const exactMatch = variantsInNewWeight.find(
      (v) => v.flavor.toLowerCase() === selectedFlavor.toLowerCase()
    );

    if (!exactMatch && variantsInNewWeight.length > 0) {
      // Fallback preference: Unflavored first, otherwise lowest price manufactured SKU
      const unflav = variantsInNewWeight.find((v) => v.isUnflavored);
      if (unflav) {
        setSelectedFlavor(unflav.flavor);
      } else {
        const cheapest = variantsInNewWeight
          .slice()
          .sort((a, b) => {
            const pA = a.listings.find((l) => l.inStock)?.currentPrice || Infinity;
            const pB = b.listings.find((l) => l.inStock)?.currentPrice || Infinity;
            return pA - pB;
          })[0];
        setSelectedFlavor(cheapest?.flavor || variantsInNewWeight[0].flavor);
      }
    }
  };

  // 6. Best Value Weight Indicator: identify the weight that gives the absolute lowest unit cost
  const bestValueWeight = useMemo(() => {
    if (availableWeights.length <= 1) return null;
    let lowestUnitCost = Infinity;
    let winningWeight: number | null = null;

    availableWeights.forEach((w) => {
      const vars = variants.filter((v) => v.weightGrams === w);
      vars.forEach((v) => {
        const metrics = resolveCardMetrics(parent, w, v.flavor);
        if (metrics && metrics.unitCostValue > 0 && metrics.unitCostValue < lowestUnitCost) {
          lowestUnitCost = metrics.unitCostValue;
          winningWeight = w;
        }
      });
    });

    return winningWeight;
  }, [availableWeights, variants, parent]);

  // 7. Resolve Metrics for the Active SKU
  const activeMetrics = useMemo<ResolvedSKUMetrics | null>(() => {
    return resolveCardMetrics(parent, selectedWeight, selectedFlavor);
  }, [parent, selectedWeight, selectedFlavor]);

  const activeVariant = activeMetrics?.activeVariant;
  const currentPrice = activeMetrics?.lowestPrice || 0;
  const mrp = activeMetrics?.mrp || Math.round(currentPrice * 1.25);
  const discountPct = activeMetrics?.discountPercent || 0;
  const storeCount = activeMetrics?.storeCount || 1;
  const bestStore = activeMetrics?.bestStore;
  const isOutOfStock = !activeMetrics?.inStock;

  // 30-Day Simulated Low
  const low30Day = Math.round(currentPrice * 0.95);

  // Top inline flavors (first 3) vs rest
  const inlineFlavors = allProductFlavors.slice(0, 3);
  const extraFlavors = allProductFlavors.slice(3);

  return (
    <article className="group flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 transition-all duration-200 hover:shadow-xl hover:border-slate-300 relative">
      <div>
        {/* Trust Badges & Image Header */}
        <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-slate-50 flex items-center justify-center p-4 border border-slate-100">
          <div className="absolute left-2.5 top-2.5 z-10 flex flex-col gap-1 items-start">
            {parent.trustBadges.trustifiedVerified && (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-sm">
                <ShieldCheck className="size-3" /> Lab Verified
              </span>
            )}
            {!parent.trustBadges.aminoSpikeTested && (
              <span className="inline-flex items-center gap-1 rounded bg-amber-500 px-2 py-0.5 text-[10px] font-mono font-bold uppercase text-white shadow-sm">
                <AlertCircle className="size-3" /> Filler Warning
              </span>
            )}
          </div>

          {onToggleCompareTray && activeVariant && (
            <button
              type="button"
              onClick={() => onToggleCompareTray(activeVariant.rawVariant, product)}
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

          {parent.imageUrl ? (
            <img
              src={parent.imageUrl}
              alt={parent.name}
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

        {/* Brand & Base Name */}
        <div className="mt-3.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-bold">
              {parent.brand}
            </span>
            <span className="text-[10px] font-mono uppercase text-slate-400 font-semibold truncate max-w-[120px]">
              {parent.formulation}
            </span>
          </div>

          <h3
            title={parent.name}
            className="line-clamp-2 text-sm font-bold text-slate-900 leading-snug mt-1 h-[40px]"
          >
            {parent.name}
          </h3>

          {/* 1. WEIGHT SELECTOR STRIP */}
          <div className="mt-3">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold mb-1.5">
              Weight Selector
            </div>
            <div className="flex flex-wrap gap-1.5">
              {availableWeights.map((w) => {
                const isSelected = selectedWeight === w;
                const isBestValue = bestValueWeight === w && availableWeights.length > 1;
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => handleWeightChange(w)}
                    className={`px-2.5 py-1 text-xs font-mono rounded-lg transition-all flex items-center gap-1 border ${
                      isSelected
                        ? "bg-slate-900 border-slate-900 text-white shadow-sm font-bold"
                        : "bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <span>{formatWeightDisplay(w)}</span>
                    {isBestValue && (
                      <span className={`text-[9px] px-1 py-0.2 rounded font-sans font-bold ${
                        isSelected ? "bg-amber-400 text-slate-950" : "bg-amber-100 text-amber-800"
                      }`}>
                        ★ Value
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. FLAVOR SELECTOR STRIP WITH POPOVER */}
          <div className="mt-2.5 relative" ref={popoverRef}>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold mb-1.5">
              Flavor Selector
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {inlineFlavors.map((flavor) => {
                const isSelected = selectedFlavor.toLowerCase() === flavor.toLowerCase();
                const status = flavorAvailabilityMap.get(flavor.toLowerCase()) || {
                  isManufactured: false,
                  inStock: false,
                  price: 0,
                };

                if (!status.isManufactured) {
                  return (
                    <span
                      key={flavor}
                      title={`Not manufactured in ${formatWeightDisplay(selectedWeight)}`}
                      className="px-2 py-0.5 text-[11px] rounded border border-dashed border-slate-200 bg-slate-50 text-slate-400 line-through opacity-50 cursor-not-allowed"
                    >
                      {flavor}
                    </span>
                  );
                }

                if (!status.inStock) {
                  return (
                    <button
                      key={flavor}
                      type="button"
                      onClick={() => setSelectedFlavor(flavor)}
                      title="Out of stock across stores"
                      className={`px-2 py-0.5 text-[11px] rounded border transition-all line-through ${
                        isSelected
                          ? "border-slate-400 bg-slate-100 text-slate-500 font-bold"
                          : "border-slate-200 bg-white text-slate-400 hover:border-slate-300"
                      }`}
                    >
                      {flavor} (OOS)
                    </button>
                  );
                }

                return (
                  <button
                    key={flavor}
                    type="button"
                    onClick={() => setSelectedFlavor(flavor)}
                    className={`px-2.5 py-0.5 text-[11px] rounded-md border transition-all truncate max-w-[130px] ${
                      isSelected
                        ? "border-emerald-600 bg-emerald-50 text-emerald-800 font-bold shadow-xs"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                    }`}
                    title={flavor}
                  >
                    {flavor}
                  </button>
                );
              })}

              {/* Popover trigger if there are more flavors */}
              {extraFlavors.length > 0 && (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setIsFlavorPopoverOpen(!isFlavorPopoverOpen)}
                    className={`px-2 py-0.5 text-[11px] rounded-md border flex items-center gap-1 font-mono transition-all ${
                      isFlavorPopoverOpen
                        ? "border-slate-800 bg-slate-800 text-white"
                        : "border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    <span>+{extraFlavors.length} more</span>
                    <ChevronDown className="size-3" />
                  </button>

                  {/* Popover Grid */}
                  {isFlavorPopoverOpen && (
                    <div className="absolute left-0 bottom-full mb-1 z-30 w-56 rounded-xl border border-slate-200 bg-white p-2.5 shadow-xl">
                      <div className="text-[10px] font-mono font-bold text-slate-400 uppercase mb-1.5 pb-1 border-b">
                        All Flavors ({allProductFlavors.length})
                      </div>
                      <div className="max-h-48 overflow-y-auto space-y-1">
                        {allProductFlavors.map((flavor) => {
                          const isSelected = selectedFlavor.toLowerCase() === flavor.toLowerCase();
                          const status = flavorAvailabilityMap.get(flavor.toLowerCase()) || {
                            isManufactured: false,
                            inStock: false,
                            price: 0,
                          };

                          return (
                            <button
                              key={flavor}
                              type="button"
                              disabled={!status.isManufactured}
                              onClick={() => {
                                setSelectedFlavor(flavor);
                                setIsFlavorPopoverOpen(false);
                              }}
                              className={`w-full text-left px-2 py-1 text-xs rounded flex items-center justify-between transition-colors ${
                                !status.isManufactured
                                  ? "text-slate-300 line-through cursor-not-allowed"
                                  : isSelected
                                  ? "bg-emerald-50 text-emerald-900 font-bold"
                                  : "text-slate-700 hover:bg-slate-100"
                              }`}
                            >
                              <span className="truncate">{flavor}</span>
                              {isSelected && <Check className="size-3 text-emerald-600 shrink-0" />}
                              {!status.inStock && status.isManufactured && (
                                <span className="text-[9px] text-red-500 font-mono">OOS</span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 3. LIVE BEST PRICE FOR SELECTED SKU */}
          <div className="mt-3.5 pt-3 border-t border-slate-100">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold mb-1">
              Live Best Price ({formatWeightDisplay(selectedWeight)} · {selectedFlavor}):
            </div>
            
            <div className="flex items-baseline justify-between gap-1">
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-mono tabular-nums font-extrabold text-slate-900">
                  {formatInr(currentPrice)}
                </span>
                {mrp > currentPrice && (
                  <span className="text-xs font-mono text-slate-400 line-through">
                    {formatInr(mrp)}
                  </span>
                )}
                {discountPct > 0 && (
                  <span className="text-[11px] font-mono font-bold text-emerald-700">
                    (-{discountPct}%)
                  </span>
                )}
              </div>

              {activeMetrics && (
                <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 shrink-0">
                  {activeMetrics.unitCostLabel}
                </span>
              )}
            </div>

            {/* Store & 30-Day Low metadata */}
            <div className="mt-1 flex items-center justify-between text-[11px] font-mono text-slate-500">
              <span className="truncate">
                via {bestStore?.storeName || "Brand Store"}{" "}
                {bestStore?.isAuthorizedSeller && (
                  <span className="text-emerald-700 font-semibold">(Authorized)</span>
                )}
              </span>
              {currentPrice > 0 && (
                <span className="text-slate-500 shrink-0">
                  30d Low: <strong className="text-slate-800 font-bold">{formatInr(low30Day)}</strong>
                </span>
              )}
            </div>

            {/* 4. FLAVOR ARBITRAGE ALERT */}
            {activeMetrics && activeMetrics.flavorTaxAmount > 0 && (
              <div className="mt-2.5 flex items-start gap-1.5 text-[11px] font-mono text-amber-900 bg-amber-50 border border-amber-200/80 p-2 rounded-lg">
                <span className="text-amber-700 font-bold shrink-0">💡 FLAVOR ARBITRAGE:</span>
                <span>
                  &ldquo;{selectedFlavor}&rdquo; carries a +{formatInr(activeMetrics.flavorTaxAmount)} (+{activeMetrics.flavorTaxPercent}%) flavor tax vs {activeMetrics.cheapestFlavorName}.
                </span>
              </div>
            )}

            {activeMetrics && activeMetrics.isUnflavored && (
              <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-mono text-emerald-900 bg-emerald-50 border border-emerald-200 p-2 rounded-lg">
                <Sparkles className="size-3 text-emerald-600 shrink-0" />
                <span>
                  Baseline Unflavored: Pure active powder without flavoring tax.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 5. DUAL ACTION BUTTONS: COMPARE STORES + BUY ON STORE DIRECT */}
      <div className="mt-4 pt-1 grid grid-cols-2 gap-2">
        {isOutOfStock ? (
          <button
            type="button"
            disabled
            className="col-span-2 flex h-10 w-full items-center justify-center rounded-xl bg-slate-100 text-xs font-mono font-bold text-slate-400 cursor-not-allowed border border-slate-200"
          >
            Out of Stock Across Stores
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={() => {
                if (activeVariant) {
                  onOpenCompareDrawer(product, activeVariant.rawVariant);
                }
              }}
              className="flex h-10 items-center justify-center gap-1 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm px-2 text-center"
            >
              <Zap className="size-3.5 text-yellow-400 fill-yellow-400 shrink-0" />
              <span className="truncate">
                Compare {storeCount} Stores
              </span>
            </button>

            <a
              href={bestStore?.affiliateUrl || "#"}
              target="_blank"
              rel="noopener sponsored"
              className="flex h-10 items-center justify-center gap-1 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-mono font-bold uppercase tracking-wider transition-all shadow-sm px-2 text-center"
            >
              <span className="truncate">
                Buy on {bestStore?.storeId === "amazon" ? "Amazon" : "Store"} ↗
              </span>
            </a>
          </>
        )}
      </div>
    </article>
  );
};
