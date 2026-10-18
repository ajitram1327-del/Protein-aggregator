"use client";

import React, { useState, useMemo } from "react";
import {
  ChevronDown,
  ChevronUp,
  X,
  RotateCcw,
  Search,
  Check,
  ShieldCheck,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { FilterState } from "./types";
import { formatInr } from "@/lib/analytics";

interface DecathlonSidebarProps {
  filters: FilterState;
  availableCategories: string[];
  availableBrands: string[];
  totalMatches: number;
  isMobileOpen: boolean;
  onFilterChange: (nextFilters: Partial<FilterState>) => void;
  onResetFilters: () => void;
  onCloseMobile: () => void;
}

const FORMULATION_OPTIONS = [
  { id: "isolate", label: "Whey Isolate", badge: ">85% Protein" },
  { id: "concentrate", label: "Whey Concentrate", badge: "70–80% Protein" },
  { id: "blend", label: "Whey Blend", badge: "Isolate + Conc" },
  { id: "plant", label: "Plant Protein", badge: "Pea / Soy / Rice" },
  { id: "casein", label: "Casein", badge: "Slow Digestion" },
];

const PRICE_PRESETS = [
  { label: "All Prices", min: 0, max: 15000 },
  { label: "Under ₹1,500", min: 0, max: 1500 },
  { label: "₹1,500 – ₹2,500", min: 1500, max: 2500 },
  { label: "₹2,500 – ₹4,000", min: 2500, max: 4000 },
  { label: "Above ₹4,000", min: 4000, max: 15000 },
];

const VALUE_PRESETS = [
  { label: "All", max: 600 },
  { label: "≤ ₹250 (Budget)", max: 250 },
  { label: "≤ ₹350 (Standard)", max: 350 },
  { label: "≤ ₹450 (Premium)", max: 450 },
];

export const DecathlonSidebar: React.FC<DecathlonSidebarProps> = ({
  filters,
  availableCategories,
  availableBrands,
  totalMatches,
  isMobileOpen,
  onFilterChange,
  onResetFilters,
  onCloseMobile,
}) => {
  // Accordion open states
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    category: true,
    formulation: true,
    price: true,
    value: true,
    brand: true,
    trust: true,
    dietary: false,
  });

  const toggleSection = (key: string) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Brand search within sidebar
  const [brandSearch, setBrandSearch] = useState("");
  const filteredBrands = useMemo(() => {
    if (!brandSearch.trim()) return availableBrands;
    return availableBrands.filter((b) =>
      b.toLowerCase().includes(brandSearch.toLowerCase().trim())
    );
  }, [availableBrands, brandSearch]);

  // Check active filter count
  const activeCount = useMemo(() => {
    let count = 0;
    if (filters.category) count++;
    if (filters.formulations && filters.formulations.length > 0) count += filters.formulations.length;
    if (filters.maxPrice < 15000) count++;
    if (filters.maxCostPer100gProtein < 600) count++;
    if (filters.selectedBrands && filters.selectedBrands.length > 0) count += filters.selectedBrands.length;
    if (filters.verifiedOnly) count++;
    if (filters.authorizedOnly) count++;
    if (filters.minPurityPct > 0) count++;
    if (filters.digestiveEnzymesOnly) count++;
    if (filters.sugarFreeOnly) count++;
    if (filters.unflavoredOnly) count++;
    return count;
  }, [filters]);

  const toggleFormulation = (fId: string) => {
    const current = filters.formulations || [];
    if (current.includes(fId)) {
      onFilterChange({ formulations: current.filter((x) => x !== fId) });
    } else {
      onFilterChange({ formulations: [...current, fId] });
    }
  };

  const toggleBrand = (b: string) => {
    const current = filters.selectedBrands || [];
    if (current.includes(b)) {
      onFilterChange({ selectedBrands: current.filter((x) => x !== b) });
    } else {
      onFilterChange({ selectedBrands: [...current, b] });
    }
  };

  const content = (
    <div className="flex flex-col h-full bg-white font-sans text-slate-900">
      {/* Header: Title + Active Count + Reset */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm tracking-tight uppercase font-mono text-slate-900">
            Filters
          </span>
          {activeCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-emerald-100 text-emerald-800">
              {activeCount}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {activeCount > 0 && (
            <button
              type="button"
              onClick={onResetFilters}
              className="flex items-center gap-1 text-xs font-mono font-semibold text-slate-500 hover:text-slate-900 transition-colors"
            >
              <RotateCcw className="size-3" />
              <span>Clear all</span>
            </button>
          )}

          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1 text-slate-400 hover:text-slate-900"
            aria-label="Close filters"
          >
            <X className="size-5" />
          </button>
        </div>
      </div>

      {/* Scrollable Filter Accordions */}
      <div className="flex-1 overflow-y-auto px-5 py-2 divide-y divide-slate-100">
        {/* 1. CATEGORY */}
        <div className="py-3.5">
          <button
            type="button"
            onClick={() => toggleSection("category")}
            className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            <span>Category</span>
            {openSections.category ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
          </button>

          {openSections.category && (
            <div className="mt-3 space-y-1.5">
              <label className="flex items-center gap-2.5 text-xs cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="radio"
                  name="sidebar-category"
                  checked={!filters.category}
                  onChange={() => onFilterChange({ category: "" })}
                  className="size-3.5 accent-slate-900"
                />
                <span className={!filters.category ? "font-bold text-slate-900" : ""}>
                  All Categories
                </span>
              </label>

              {[
                { id: "protein", aliases: ["protein", "whey", "plant"], label: "Whey & Plant Protein" },
                { id: "creatine", aliases: ["creatine"], label: "Creatine Monohydrate" },
                { id: "pre_workout", aliases: ["pre_workout", "preworkout"], label: "Pre-Workout & Pump" },
                { id: "mass_gainer", aliases: ["mass_gainer", "mass_gainers", "gainer", "gainers"], label: "Mass Gainers" },
                { id: "snacks", aliases: ["snacks", "snack", "protein_snacks"], label: "Protein Snacks & Bars" },
              ].map((c) => {
                const activeCat = (filters.category || "").toLowerCase();
                const isSelected = activeCat === c.id || c.aliases.includes(activeCat);
                return (
                  <label key={c.id} className="flex items-center gap-2.5 text-xs cursor-pointer text-slate-700 hover:text-slate-900">
                    <input
                      type="radio"
                      name="sidebar-category"
                      checked={isSelected}
                      onChange={() => onFilterChange({ category: c.id })}
                      className="size-3.5 accent-emerald-600"
                    />
                    <span className={isSelected ? "font-bold text-emerald-800" : ""}>
                      {c.label}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* 2. FORMULATION */}
        <div className="py-3.5">
          <button
            type="button"
            onClick={() => toggleSection("formulation")}
            className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            <span>Formulation / Type</span>
            {openSections.formulation ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
          </button>

          {openSections.formulation && (
            <div className="mt-3 space-y-2">
              {FORMULATION_OPTIONS.map((f) => {
                const isChecked = filters.formulations?.includes(f.id);
                return (
                  <label
                    key={f.id}
                    className="flex items-center justify-between text-xs cursor-pointer text-slate-700 hover:text-slate-900"
                  >
                    <div className="flex items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleFormulation(f.id)}
                        className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                      />
                      <span className={isChecked ? "font-bold text-slate-900" : ""}>{f.label}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">{f.badge}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* 3. PRICE RANGE */}
        <div className="py-3.5">
          <button
            type="button"
            onClick={() => toggleSection("price")}
            className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            <span>Price Range</span>
            {openSections.price ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
          </button>

          {openSections.price && (
            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-500">Max Ask:</span>
                <span className="font-bold text-slate-900">{formatInr(filters.maxPrice)}</span>
              </div>

              <input
                type="range"
                min="500"
                max="15000"
                step="250"
                value={filters.maxPrice}
                onChange={(e) => onFilterChange({ maxPrice: Number(e.target.value) })}
                className="w-full accent-slate-900 cursor-pointer"
                aria-label="Filter by maximum price"
              />

              <div className="flex flex-wrap gap-1.5 pt-1">
                {PRICE_PRESETS.map((p) => {
                  const isActive = filters.maxPrice === p.max;
                  return (
                    <button
                      key={p.label}
                      type="button"
                      onClick={() => onFilterChange({ maxPrice: p.max })}
                      className={`text-[10px] font-mono px-2 py-1 rounded-sm border transition-colors ${
                        isActive
                          ? "bg-slate-900 text-white font-bold border-slate-900"
                          : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* 4. ACTIVE YIELD / TRUE VALUE */}
        <div className="py-3.5">
          <button
            type="button"
            onClick={() => toggleSection("value")}
            className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            <span>True Value (₹/100g Prot)</span>
            {openSections.value ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
          </button>

          {openSections.value && (
            <div className="mt-3 space-y-3">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-500">Max Pure Protein Cost:</span>
                <span className="font-bold text-emerald-700">≤ ₹{filters.maxCostPer100gProtein}</span>
              </div>

              <input
                type="range"
                min="150"
                max="600"
                step="25"
                value={filters.maxCostPer100gProtein}
                onChange={(e) => onFilterChange({ maxCostPer100gProtein: Number(e.target.value) })}
                className="w-full accent-emerald-600 cursor-pointer"
                aria-label="Filter by maximum cost per 100g protein"
              />

              <div className="flex flex-wrap gap-1.5">
                {VALUE_PRESETS.map((v) => {
                  const isActive = filters.maxCostPer100gProtein === v.max;
                  return (
                    <button
                      key={v.label}
                      type="button"
                      onClick={() => onFilterChange({ maxCostPer100gProtein: v.max })}
                      className={`text-[10px] font-mono px-2 py-1 rounded-sm border transition-colors ${
                        isActive
                          ? "bg-emerald-700 text-white font-bold border-emerald-700"
                          : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      {v.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* 5. BRANDS */}
        {availableBrands.length > 0 && (
          <div className="py-3.5">
            <button
              type="button"
              onClick={() => toggleSection("brand")}
              className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
            >
              <span>Brands ({availableBrands.length})</span>
              {openSections.brand ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
            </button>

            {openSections.brand && (
              <div className="mt-3 space-y-2">
                {availableBrands.length > 6 && (
                  <div className="relative mb-2">
                    <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search brands..."
                      value={brandSearch}
                      onChange={(e) => setBrandSearch(e.target.value)}
                      className="w-full pl-8 pr-3 py-1 text-xs border border-slate-200 rounded-sm outline-none focus:border-slate-900"
                    />
                  </div>
                )}

                <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1">
                  {filteredBrands.map((b) => {
                    const isChecked = filters.selectedBrands?.includes(b);
                    return (
                      <label
                        key={b}
                        className="flex items-center gap-2.5 text-xs cursor-pointer text-slate-700 hover:text-slate-900"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleBrand(b)}
                          className="size-3.5 rounded-xs border-slate-300 accent-slate-900"
                        />
                        <span className={isChecked ? "font-bold text-slate-900" : ""}>{b}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 6. TRUST & VERIFICATION */}
        <div className="py-3.5">
          <button
            type="button"
            onClick={() => toggleSection("trust")}
            className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            <span>Trust & Verification</span>
            {openSections.trust ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
          </button>

          {openSections.trust && (
            <div className="mt-3 space-y-2 text-xs">
              <label className="flex items-center gap-2.5 cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={filters.verifiedOnly}
                  onChange={(e) => onFilterChange({ verifiedOnly: e.target.checked })}
                  className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                />
                <span className="flex items-center gap-1.5 font-medium">
                  <ShieldCheck className="size-3.5 text-emerald-700" />
                  <span>3rd-Party Lab Verified</span>
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={filters.authorizedOnly}
                  onChange={(e) => onFilterChange({ authorizedOnly: e.target.checked })}
                  className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                />
                <span className="font-medium">Authorized Retailers Only</span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={filters.minPurityPct >= 75}
                  onChange={(e) => onFilterChange({ minPurityPct: e.target.checked ? 75 : 0 })}
                  className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                />
                <span className="font-medium">Min 75% Purity (Filler-Free)</span>
              </label>
            </div>
          )}
        </div>

        {/* 7. DIETARY PREFERENCES */}
        <div className="py-3.5">
          <button
            type="button"
            onClick={() => toggleSection("dietary")}
            className="flex items-center justify-between w-full text-left font-mono text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            <span>Dietary & Digestion</span>
            {openSections.dietary ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}
          </button>

          {openSections.dietary && (
            <div className="mt-3 space-y-2 text-xs">
              <label className="flex items-center gap-2.5 cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={filters.unflavoredOnly}
                  onChange={(e) => onFilterChange({ unflavoredOnly: e.target.checked })}
                  className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                />
                <span>Unflavored / Raw Only</span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={filters.sugarFreeOnly}
                  onChange={(e) => onFilterChange({ sugarFreeOnly: e.target.checked })}
                  className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                />
                <span>Zero Added Sugar</span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer text-slate-700 hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={filters.digestiveEnzymesOnly}
                  onChange={(e) => onFilterChange({ digestiveEnzymesOnly: e.target.checked })}
                  className="size-3.5 rounded-xs border-slate-300 accent-emerald-600"
                />
                <span>Digestive Enzymes Added</span>
              </label>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Footer Apply Button */}
      <div className="p-4 border-t border-slate-200 lg:hidden">
        <button
          type="button"
          onClick={onCloseMobile}
          className="w-full py-2.5 bg-slate-900 text-white font-mono text-xs font-bold uppercase tracking-wider rounded-sm hover:bg-slate-800"
        >
          View {totalMatches} Matches
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sticky Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 bg-white border border-slate-200 rounded-sm self-start shadow-xs sticky top-32">
        {content}
      </aside>

      {/* Mobile Slide-over Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden lg:hidden">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
          />
          <div className="fixed inset-y-0 left-0 max-w-xs w-full shadow-2xl z-50">
            {content}
          </div>
        </div>
      )}
    </>
  );
};
