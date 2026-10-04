"use client";

import React from "react";
import { Search, X, SlidersHorizontal, ChevronDown } from "lucide-react";
import { FilterState, SortOption } from "./types";

interface CatalogControlsProps {
  filters: FilterState;
  availableCategories: string[];
  availableBrands: string[];
  minPriceLimit?: number;
  maxPriceLimit?: number;
  totalMatches: number;
  isMobileFilterOpen: boolean;
  onFilterChange: (nextFilters: Partial<FilterState>) => void;
  onResetFilters: () => void;
  setIsMobileFilterOpen: (open: boolean) => void;
}

export const CatalogControls: React.FC<CatalogControlsProps> = ({
  filters,
  availableCategories,
  availableBrands,
  minPriceLimit = 0,
  maxPriceLimit = 5000,
  totalMatches,
  isMobileFilterOpen,
  onFilterChange,
  onResetFilters,
  setIsMobileFilterOpen,
}) => {
  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between lg:col-span-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={filters.query}
            onChange={(e) => onFilterChange({ query: e.target.value })}
            placeholder="Search products or brands..."
            className="h-10 w-full rounded-full border border-slate-200 bg-white pl-10 pr-4 text-sm outline-none transition focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsMobileFilterOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold lg:hidden"
          >
            <SlidersHorizontal className="size-4" /> Filters
          </button>

          <div className="relative">
            <select
              aria-label="Sort products"
              value={filters.sort}
              onChange={(e) =>
                onFilterChange({ sort: e.target.value as SortOption })
              }
              className="h-10 appearance-none rounded-lg border border-slate-200 bg-white pl-3 pr-8 text-xs font-semibold outline-none"
            >
              <option value="featured">Featured</option>
              <option value="price-asc">Price: Low to High</option>
              <option value="price-desc">Price: High to Low</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
          </div>
        </div>
      </div>

      <aside
        className={`${
          isMobileFilterOpen
            ? "fixed inset-0 z-50 overflow-y-auto bg-white p-6"
            : "hidden"
        } lg:static lg:z-auto lg:block lg:w-64 shrink-0 glass-card p-6 self-start`}
      >
        <div className="flex items-center justify-between mb-6">
           <h2 className="font-bold text-lg text-slate-800 tracking-wide">Filters</h2>
           <div className="flex items-center gap-2">
             <button 
               onClick={onResetFilters}
               className="text-xs text-slate-500 font-semibold hover:text-slate-800 transition-colors"
             >
               Clear all
             </button>
             <button
               type="button"
               onClick={() => setIsMobileFilterOpen(false)}
               className="p-1 lg:hidden"
             >
               <X className="size-5" />
             </button>
           </div>
        </div>

        {availableCategories.length > 0 && (
          <div className="mb-8">
            <h3 className="text-xs font-bold text-slate-400 mb-4 uppercase tracking-widest">Category</h3>
            <div className="flex flex-col gap-3">
              <label className="flex items-center gap-3 cursor-pointer text-sm group">
                <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-all ${!filters.category ? 'border-[var(--accent-green)]' : 'border-slate-300 group-hover:border-[var(--accent-green)]'}`}>
                  {!filters.category && <div className="w-2 h-2 rounded-full bg-[var(--accent-green)]" />}
                </div>
                <input type="radio" name="category" checked={!filters.category} onChange={() => onFilterChange({ category: "" })} className="hidden" />
                <span className={!filters.category ? "font-bold text-slate-800" : "text-slate-600 group-hover:text-slate-900 transition-colors"}>ALL CATEGORIES</span>
              </label>
              {availableCategories.map(c => (
                <label key={c} className="flex items-center gap-3 cursor-pointer text-sm group">
                  <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-all ${filters.category === c ? 'border-[var(--accent-green)]' : 'border-slate-300 group-hover:border-[var(--accent-green)]'}`}>
                    {filters.category === c && <div className="w-2 h-2 rounded-full bg-[var(--accent-green)]" />}
                  </div>
                  <input type="radio" name="category" checked={filters.category === c} onChange={() => onFilterChange({ category: c })} className="hidden" />
                  <span className={filters.category === c ? "font-bold text-slate-800" : "text-slate-600 group-hover:text-slate-900 transition-colors"}>{c.replace('_', ' ').toUpperCase()}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="mb-8 border-t border-slate-100 pt-6">
          <h3 className="text-xs font-bold text-slate-400 mb-4 uppercase tracking-widest">Max Price</h3>
          <div className="text-[var(--accent-green)] font-mono text-sm mb-3 font-bold">₹{filters.maxPrice}</div>
          <input 
            type="range" min="100" max="15000" step="100" value={filters.maxPrice} onChange={(e) => onFilterChange({ maxPrice: Number(e.target.value) })}
            className="w-full accent-[var(--accent-green)]"
          />
        </div>

        <div className="mb-8 border-t border-slate-100 pt-6">
          <h3 className="text-xs font-bold text-slate-400 mb-4 uppercase tracking-widest">Quality Standard</h3>
          <label className="flex items-center gap-3 cursor-pointer text-sm group">
            <div className={`w-4 h-4 rounded-[4px] border flex items-center justify-center transition-all ${filters.verifiedOnly ? 'border-[var(--accent-green)] bg-[var(--accent-green)]' : 'border-slate-300 group-hover:border-[var(--accent-green)]'}`}>
              {filters.verifiedOnly && <span className="text-white text-xs">✓</span>}
            </div>
            <input type="checkbox" checked={filters.verifiedOnly} onChange={(e) => onFilterChange({ verifiedOnly: e.target.checked })} className="hidden" />
            <span className="text-slate-600 font-medium group-hover:text-slate-900 transition-colors">🛡️ Lab Verified</span>
          </label>
        </div>

        {availableBrands.length > 0 && (
          <div className="mb-4 border-t border-slate-100 pt-6">
            <h3 className="text-xs font-bold text-slate-400 mb-4 uppercase tracking-widest">Brands</h3>
            <div className="flex flex-col gap-3 max-h-64 overflow-y-auto pr-2">
              {availableBrands.map(b => (
                <label key={b} className="flex items-center gap-3 cursor-pointer text-sm group">
                  <div className={`w-4 h-4 rounded-[4px] border flex items-center justify-center transition-all ${filters.selectedBrands.includes(b) ? 'border-[var(--accent-green)] bg-[var(--accent-green)]' : 'border-slate-300 group-hover:border-[var(--accent-green)]'}`}>
                    {filters.selectedBrands.includes(b) && <span className="text-white text-xs">✓</span>}
                  </div>
                  <input 
                    type="checkbox" 
                    checked={filters.selectedBrands.includes(b)} 
                    onChange={(e) => {
                      if (e.target.checked) onFilterChange({ selectedBrands: [...filters.selectedBrands, b] });
                      else onFilterChange({ selectedBrands: filters.selectedBrands.filter(x => x !== b) });
                    }} 
                    className="hidden"
                  />
                  <span className="text-slate-600 font-medium group-hover:text-slate-900 transition-colors">{b}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={() => setIsMobileFilterOpen(false)}
          className="mt-4 w-full rounded-lg bg-[var(--accent-green)] py-2.5 text-xs font-bold text-white lg:hidden transition-colors hover:bg-green-700"
        >
          View {totalMatches} results
        </button>
      </aside>
    </>
  );
};
