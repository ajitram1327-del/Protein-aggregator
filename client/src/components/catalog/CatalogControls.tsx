"use client";

import React from "react";
import { Search, X, SlidersHorizontal, ChevronDown, ShieldCheck, Sparkles, Filter, Check } from "lucide-react";
import { FilterState, SortOption } from "./types";

interface CatalogControlsProps {
  filters: FilterState;
  availableCategories: string[];
  availableBrands: string[];
  totalMatches: number;
  isMobileFilterOpen: boolean;
  onFilterChange: (nextFilters: Partial<FilterState>) => void;
  onResetFilters: () => void;
  setIsMobileFilterOpen: (open: boolean) => void;
}

const FORMULATION_OPTIONS = [
  { id: "isolate", label: "Whey Isolate", desc: ">85% prot, low lactose" },
  { id: "concentrate", label: "Whey Concentrate", desc: "70–80% prot, budget" },
  { id: "blend", label: "Whey Blend", desc: "Isolate + Conc combo" },
  { id: "plant", label: "Plant Protein", desc: "Pea / Soy / Rice" },
  { id: "casein", label: "Casein", desc: "Slow nighttime digestion" },
];

const VALUE_PRESETS = [
  { label: "All", max: 600 },
  { label: "< ₹250 (Budget Beast)", max: 250 },
  { label: "< ₹300 (Sweet Spot)", max: 300 },
  { label: "< ₹400 (Premium)", max: 400 },
];

export const CatalogControls: React.FC<CatalogControlsProps> = ({
  filters,
  availableCategories,
  availableBrands,
  totalMatches,
  isMobileFilterOpen,
  onFilterChange,
  onResetFilters,
  setIsMobileFilterOpen,
}) => {
  const toggleFormulation = (fId: string) => {
    const current = filters.formulations || [];
    if (current.includes(fId)) {
      onFilterChange({ formulations: current.filter((x) => x !== fId) });
    } else {
      onFilterChange({ formulations: [...current, fId] });
    }
  };

  return (
    <>
      {/* Top Search Bar & Sort Dropdown */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between lg:col-span-2">
        <div className="relative flex-1 max-w-lg">
          <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={filters.query}
            onChange={(e) => onFilterChange({ query: e.target.value })}
            placeholder="Search whey, isolate, brand, or flavor..."
            className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-4 text-sm font-medium outline-none transition focus:border-slate-900 focus:ring-1 focus:ring-slate-900 shadow-sm"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsMobileFilterOpen(true)}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-mono font-bold uppercase tracking-wider text-slate-700 shadow-sm lg:hidden hover:bg-slate-50"
          >
            <SlidersHorizontal className="size-4" />
            <span>Filters ({totalMatches})</span>
          </button>

          <div className="relative">
            <select
              aria-label="Sort products"
              value={filters.sort}
              onChange={(e) =>
                onFilterChange({ sort: e.target.value as SortOption })
              }
              className="h-11 appearance-none rounded-xl border border-slate-200 bg-white pl-3.5 pr-9 text-xs font-mono font-bold uppercase tracking-wider text-slate-800 outline-none shadow-sm focus:border-slate-900 cursor-pointer"
            >
              <option value="featured">Featured (Verified First)</option>
              <option value="value-asc">Best Value (₹/100g Prot)</option>
              <option value="price-asc">Price: Low to High</option>
              <option value="price-desc">Price: High to Low</option>
              <option value="purity-desc">Highest Purity %</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
          </div>
        </div>
      </div>

      {/* 4-Gate Decision Filter Sidebar */}
      <aside
        className={`${
          isMobileFilterOpen
            ? "fixed inset-0 z-50 overflow-y-auto bg-white p-6"
            : "hidden"
        } lg:static lg:z-auto lg:block lg:w-72 shrink-0 bg-white rounded-2xl border border-slate-200 p-5 self-start shadow-sm space-y-6`}
      >
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Filter className="size-4 text-emerald-600" />
            <h2 className="font-mono font-bold text-sm uppercase tracking-wider text-slate-900">
              Decision Gates
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onResetFilters}
              className="text-xs text-slate-500 font-mono font-semibold hover:text-slate-900 transition-colors underline"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => setIsMobileFilterOpen(false)}
              className="p-1 lg:hidden text-slate-400 hover:text-slate-900"
            >
              <X className="size-5" />
            </button>
          </div>
        </div>

        {/* GATE 1: Formulation Lock */}
        <div>
          <div className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center justify-between">
            <span>Gate 1 · Formulation</span>
            <span className="text-[10px] text-slate-400">Multiple</span>
          </div>
          <div className="flex flex-col gap-2">
            {FORMULATION_OPTIONS.map((form) => {
              const isChecked = filters.formulations?.includes(form.id);
              return (
                <button
                  key={form.id}
                  type="button"
                  onClick={() => toggleFormulation(form.id)}
                  className={`flex items-start justify-between text-left p-2.5 rounded-xl border text-xs transition-all ${
                    isChecked
                      ? "border-emerald-600 bg-emerald-50/70 text-emerald-950 font-bold shadow-sm"
                      : "border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700"
                  }`}
                >
                  <div>
                    <div className="font-semibold">{form.label}</div>
                    <div className="text-[10px] text-slate-500 font-normal mt-0.5">{form.desc}</div>
                  </div>
                  <div
                    className={`size-4 rounded-md border flex items-center justify-center shrink-0 mt-0.5 transition-all ${
                      isChecked
                        ? "border-emerald-600 bg-emerald-600 text-white"
                        : "border-slate-300 bg-white"
                    }`}
                  >
                    {isChecked && <Check className="size-3" />}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* GATE 2: True Value Filter (₹ / 100g Pure Protein) */}
        <div className="pt-4 border-t border-slate-100">
          <div className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center justify-between">
            <span>Gate 2 · True Value</span>
            <span className="text-emerald-700 font-bold font-mono">
              ≤ ₹{filters.maxCostPer100gProtein}/100g
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mb-3">
            Filters by net protein cost, eliminating oversized serving tricks.
          </p>

          <input
            type="range"
            min="150"
            max="600"
            step="25"
            value={filters.maxCostPer100gProtein}
            onChange={(e) => onFilterChange({ maxCostPer100gProtein: Number(e.target.value) })}
            className="w-full accent-emerald-600 cursor-pointer"
          />

          {/* Quick presets */}
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            {VALUE_PRESETS.map((preset) => {
              const active = filters.maxCostPer100gProtein === preset.max;
              return (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => onFilterChange({ maxCostPer100gProtein: preset.max })}
                  className={`text-[10px] font-mono px-2 py-1 rounded-lg border transition-all ${
                    active
                      ? "border-emerald-600 bg-emerald-600 text-white font-bold"
                      : "border-slate-200 text-slate-600 hover:border-slate-300 bg-white"
                  }`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* GATE 3: Purity & Trust Thresholds */}
        <div className="pt-4 border-t border-slate-100 space-y-3">
          <div className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-widest mb-1">
            Gate 3 · Purity & Trust
          </div>

          <label className="flex items-center gap-3 cursor-pointer text-xs group">
            <input
              type="checkbox"
              checked={filters.verifiedOnly}
              onChange={(e) => onFilterChange({ verifiedOnly: e.target.checked })}
              className="size-4 rounded border-slate-300 text-emerald-600 accent-emerald-600"
            />
            <span className="font-semibold text-slate-800 flex items-center gap-1.5">
              <ShieldCheck className="size-3.5 text-emerald-600" />
              <span>3rd-Party Lab Verified Only</span>
            </span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer text-xs group">
            <input
              type="checkbox"
              checked={filters.minPurityPct >= 75}
              onChange={(e) => onFilterChange({ minPurityPct: e.target.checked ? 75 : 0 })}
              className="size-4 rounded border-slate-300 text-emerald-600 accent-emerald-600"
            />
            <span className="text-slate-700 font-medium">
              Min 75% Protein per Scoop (No Fillers)
            </span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer text-xs group">
            <input
              type="checkbox"
              checked={filters.authorizedOnly}
              onChange={(e) => onFilterChange({ authorizedOnly: e.target.checked })}
              className="size-4 rounded border-slate-300 text-emerald-600 accent-emerald-600"
            />
            <span className="text-slate-700 font-medium">
              Authorized Sellers Only (Exclude Grey Market)
            </span>
          </label>
        </div>

        {/* GATE 4: Dietary & Digestion Flags */}
        <div className="pt-4 border-t border-slate-100 space-y-3">
          <div className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-widest mb-1">
            Gate 4 · Dietary & Digestion
          </div>

          <label className="flex items-center gap-3 cursor-pointer text-xs group">
            <input
              type="checkbox"
              checked={filters.digestiveEnzymesOnly}
              onChange={(e) => onFilterChange({ digestiveEnzymesOnly: e.target.checked })}
              className="size-4 rounded border-slate-300 text-emerald-600 accent-emerald-600"
            />
            <span className="text-slate-700 font-medium">
              Digestive Enzymes (DigeZyme / Papain)
            </span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer text-xs group">
            <input
              type="checkbox"
              checked={filters.sugarFreeOnly}
              onChange={(e) => onFilterChange({ sugarFreeOnly: e.target.checked })}
              className="size-4 rounded border-slate-300 text-emerald-600 accent-emerald-600"
            />
            <span className="text-slate-700 font-medium">
              Zero Added Sugar / Sucralose-Free
            </span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer text-xs group">
            <input
              type="checkbox"
              checked={filters.unflavoredOnly}
              onChange={(e) => onFilterChange({ unflavoredOnly: e.target.checked })}
              className="size-4 rounded border-slate-300 text-emerald-600 accent-emerald-600"
            />
            <span className="text-slate-700 font-medium">
              Unflavored / Raw Only (No Flavor Tax)
            </span>
          </label>
        </div>

        {/* Brands Filter */}
        {availableBrands.length > 0 && (
          <div className="pt-4 border-t border-slate-100">
            <div className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-widest mb-3">
              Brands ({availableBrands.length})
            </div>
            <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
              {availableBrands.map((b) => (
                <label key={b} className="flex items-center gap-2.5 cursor-pointer text-xs group">
                  <input
                    type="checkbox"
                    checked={filters.selectedBrands.includes(b)}
                    onChange={(e) => {
                      if (e.target.checked) onFilterChange({ selectedBrands: [...filters.selectedBrands, b] });
                      else onFilterChange({ selectedBrands: filters.selectedBrands.filter((x) => x !== b) });
                    }}
                    className="size-3.5 rounded border-slate-300 text-emerald-600 accent-emerald-600"
                  />
                  <span className="text-slate-700 font-medium group-hover:text-slate-900 transition-colors">
                    {b}
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Mobile View Results CTA */}
        <button
          type="button"
          onClick={() => setIsMobileFilterOpen(false)}
          className="mt-4 w-full rounded-xl bg-slate-900 py-3 text-xs font-mono font-bold uppercase tracking-wider text-white lg:hidden transition-colors hover:bg-slate-800"
        >
          View {totalMatches} Matches
        </button>
      </aside>
    </>
  );
};
