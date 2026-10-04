"use client";

import React from "react";
import { Info, ShoppingCart } from "lucide-react";
import { ProductItem } from "./types";

interface ProductCardProps {
  product: ProductItem;
  isSaved?: boolean;
  onToggleSave?: (id: string | number) => void;
  onSelect?: (product: ProductItem) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onSelect,
}) => {
  const hasDiscount = Boolean(product.oldPrice && product.oldPrice > product.price);
  const discountPercent = hasDiscount
    ? Math.round((1 - product.price / product.oldPrice!) * 100)
    : 0;

  const formattedPrice = (product.price || 0).toLocaleString("en-IN");
  
  // Calculate True Cost per Gram of Pure Protein
  let trueCostPerGram: number | null = null;
  if (product.price && product.weightGrams && product.proteinPerServing && product.servingSizeGrams) {
    const totalProtein = product.weightGrams * (product.proteinPerServing / product.servingSizeGrams);
    trueCostPerGram = product.price / totalProtein;
  }

  return (
    <article className="group flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-3 transition-all duration-200 hover:shadow-md">
      <div>
        <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-slate-50 flex items-center justify-center p-4">
          {product.tag && (
            <span className="absolute left-2 top-2 z-10 rounded-md bg-emerald-50 border border-emerald-200 px-2 py-1 text-xs font-semibold text-emerald-700">
              {product.tag}
            </span>
          )}

          {product.image ? (
            <img
              src={product.image}
              alt={product.name || "Product image"}
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLElement).style.display = "none";
              }}
              className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105 mix-blend-multiply"
            />
          ) : (
            <div className="text-xs text-slate-500 font-medium">No Image</div>
          )}
        </div>

        <div className="mt-4 px-1">
          <h3
            title={product.name}
            className="line-clamp-2 text-sm font-semibold text-slate-900 leading-snug h-[40px]"
          >
            {product.name || "Untitled Product"}
          </h3>
          <p className="text-xs text-slate-500 mt-1">{product.brand}</p>

          <div className="mt-3 flex flex-col gap-1">
            <span className="text-lg font-mono tabular-nums font-bold text-slate-900">
              ₹{formattedPrice}
            </span>
            {trueCostPerGram && (
              <span className="text-xs font-mono tabular-nums font-medium text-emerald-700 bg-emerald-50 px-2 py-1 rounded w-fit border border-emerald-100">
                ₹{trueCostPerGram.toFixed(2)} / g pure protein
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-2 px-1 pb-1">
        <button
          type="button"
          onClick={() => onSelect && onSelect(product)}
          className="flex h-10 flex-1 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50 text-[14px] font-semibold text-slate-700 transition-colors hover:bg-slate-100 hover:border-slate-300"
        >
          Compare Prices
        </button>
      </div>
    </article>
  );
};
