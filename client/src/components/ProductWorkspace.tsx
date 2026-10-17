'use client';

import React, { useState, useMemo, useTransition } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Bell, ArrowUpRight, ShieldAlert, ShieldCheck, Activity, DollarSign } from 'lucide-react';

export interface HistoricalPricePoint {
  date: string;
  price: number;
}

export interface ResellerOffer {
  seller: string;
  price: number;
  url: string;
  isAvailable: boolean;
}

export interface HydratedVariant {
  id: string | number;
  variantHash?: string;
  variant_hash?: string;
  flavor: string;
  weightDisplay: string;
  weightGrams?: number;
  packCount: number;
  lowestPrice: number;
  bestSource: string;
  redirectUrl: string;
  costPer100gPure: number;
  flavorTaxPct: number;
  calculatedPurityPct?: number;
  offers: ResellerOffer[];
  priceHistory: HistoricalPricePoint[];
}

export interface MasterProductData {
  id: string;
  brand: string;
  lineName: string;
  categorySilo: string;
  specs: {
    purity: string | number;
    isSpiked: boolean;
    diaasScore: number;
  };
  variants: HydratedVariant[];
}

interface ProductWorkspaceProps {
  data: MasterProductData;
}

/**
 * Format helper to screen floating point precision leaks.
 * Enforces explicit rounding formatting rules across layouts.
 */
function formatNumber(val: number | string | undefined | null, decimals: number = 1): string {
  if (val === undefined || val === null || val === '') return '0.0';
  const num = typeof val === 'number' ? val : parseFloat(String(val).replace(/[^\d.-]/g, ''));
  if (isNaN(num) || !isFinite(num)) return '0.0';
  return num.toFixed(decimals);
}

function formatCurrency(val: number | undefined | null): string {
  if (val === undefined || val === null || isNaN(val)) return '0';
  return Math.round(val).toLocaleString('en-IN');
}

export function ProductWorkspace({ data }: ProductWorkspaceProps) {
  const { brand, lineName, specs, variants } = data;
  const [, startTransition] = useTransition();

  // 1. Isolate clean, deterministic layout option sets
  const distinctFlavors = useMemo(() => {
    return Array.from(new Set(variants.map(v => v.flavor))).filter(Boolean);
  }, [variants]);

  const distinctSizes = useMemo(() => {
    return Array.from(new Set(variants.map(v => v.weightDisplay))).filter(Boolean);
  }, [variants]);

  // 2. Local state trackers initialized safely
  const initialVariant = variants[0] || null;
  const [selectedFlavor, setSelectedFlavor] = useState<string>(initialVariant?.flavor || distinctFlavors[0] || '');
  const [selectedSize, setSelectedSize] = useState<string>(initialVariant?.weightDisplay || distinctSizes[0] || '');
  const [isWatching, setIsWatching] = useState<boolean>(false);

  // 3. SECURE PROPERTY MATCHING CONTRACTS: Synchronized Variant Resolution Engine
  // Prevents parent-child property bleeding by strictly pairing size and flavor
  const availableSizesForCurrentFlavor = useMemo(() => {
    return new Set(
      variants
        .filter(v => v.flavor === selectedFlavor)
        .map(v => v.weightDisplay)
    );
  }, [variants, selectedFlavor]);

  const availableFlavorsForCurrentSize = useMemo(() => {
    return new Set(
      variants
        .filter(v => v.weightDisplay === selectedSize)
        .map(v => v.flavor)
    );
  }, [variants, selectedSize]);

  const activeVariant = useMemo(() => {
    // Exact match for current selection
    const exact = variants.find(
      v => v.flavor === selectedFlavor && v.weightDisplay === selectedSize
    );
    if (exact) return exact;

    // Fallback: Pick first variant of current flavor if size is invalid
    const flavorFallback = variants.find(v => v.flavor === selectedFlavor);
    if (flavorFallback) return flavorFallback;

    return variants[0] || null;
  }, [variants, selectedFlavor, selectedSize]);

  // Handle flavor selection with React 19 concurrent transition and size re-synchronization
  const handleFlavorSelect = (flavor: string) => {
    startTransition(() => {
      setSelectedFlavor(flavor);
      // If currently selected size doesn't exist for this flavor, auto-snap to flavor's first size
      const validSizes = variants.filter(v => v.flavor === flavor).map(v => v.weightDisplay);
      if (!validSizes.includes(selectedSize) && validSizes.length > 0) {
        setSelectedSize(validSizes[0]);
      }
    });
  };

  // Handle size selection with React 19 concurrent transition
  const handleSizeSelect = (size: string) => {
    startTransition(() => {
      setSelectedSize(size);
    });
  };

  // 4. Dynamic consumer evaluation badge system (deterministic mathematical thresholds)
  const marketRating = useMemo(() => {
    const cost = activeVariant?.costPer100gPure || 0;
    if (cost <= 0) return { text: 'Out of Stock', style: 'bg-slate-900 text-slate-500 border-slate-800' };
    if (cost < 260) return { text: '🔥 Elite Value Pick', style: 'bg-emerald-950/80 text-emerald-400 border-emerald-800/80' };
    if (cost < 340) return { text: '👍 Fair Market Price', style: 'bg-slate-900 text-slate-300 border-slate-800' };
    return { text: '⚠️ Premium Cost Profile', style: 'bg-amber-950/40 text-amber-500 border-amber-900/40' };
  }, [activeVariant]);

  // Masked precision values to eliminate floating decimal drops
  const displayPurity = useMemo(() => {
    if (activeVariant?.calculatedPurityPct !== undefined && activeVariant.calculatedPurityPct > 0) {
      return `${formatNumber(activeVariant.calculatedPurityPct, 1)}%`;
    }
    return `${formatNumber(specs.purity, 1)}%`;
  }, [activeVariant, specs.purity]);

  const displayCostPer100g = useMemo(() => {
    return formatNumber(activeVariant?.costPer100gPure, 1);
  }, [activeVariant?.costPer100gPure]);

  const displayFlavorTax = useMemo(() => {
    const tax = activeVariant?.flavorTaxPct || 0;
    return tax > 0 ? `+${formatNumber(tax, 1)}% premium charge` : '0% Base SKU Profile';
  }, [activeVariant?.flavorTaxPct]);

  const displayDiaas = useMemo(() => {
    return formatNumber(specs.diaasScore, 2);
  }, [specs.diaasScore]);

  const canonicalVariantId = activeVariant?.variantHash || activeVariant?.variant_hash || activeVariant?.id || 'N/A';

  return (
    <div className="max-w-5xl mx-auto border border-slate-900 bg-slate-900/20 rounded-3xl backdrop-blur-xl shadow-2xl overflow-hidden font-sans">
      
      {/* Dynamic Header Frame */}
      <div className="p-6 sm:p-8 border-b border-slate-900 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 bg-gradient-to-b from-slate-900/40 to-transparent">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold tracking-widest text-slate-500 uppercase bg-slate-950 border border-slate-800/80 px-2 py-0.5 rounded">
              MATRIX ID: {data.id}
            </span>
            <span className="text-[10px] font-mono font-bold tracking-widest text-slate-600 uppercase bg-slate-950 border border-slate-800/80 px-2 py-0.5 rounded">
              SKU: {String(canonicalVariantId).slice(0, 10)}
            </span>
            {specs.isSpiked ? (
              <span className="flex items-center gap-1 text-[10px] font-bold bg-rose-950/40 text-rose-400 border border-rose-900/50 px-2 py-0.5 rounded animate-pulse">
                <ShieldAlert className="w-3 h-3" /> SPIKE WARNING
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[10px] font-bold bg-emerald-950/40 text-emerald-400 border border-emerald-900/50 px-2 py-0.5 rounded">
                <ShieldCheck className="w-3 h-3" /> LAB VERIFIED
              </span>
            )}
          </div>
          <h2 className="text-xs font-mono font-bold tracking-widest text-slate-400 uppercase mt-4">{brand}</h2>
          <h1 className="text-3xl font-black tracking-tight text-neutral-50 mt-1">{lineName}</h1>
          
          <div className="flex flex-wrap gap-2 mt-4">
            <span className={`text-xs font-bold px-3 py-1 rounded-lg border ${marketRating.style}`}>
              {marketRating.text}
            </span>
            <span className="text-xs font-medium bg-slate-900 text-slate-400 border border-slate-800/80 px-3 py-1 rounded-lg">
              🎯 {displayPurity} True Protein Content
            </span>
          </div>
        </div>

        {/* Live Sticker Pricing Focus Window */}
        <div className="bg-slate-950/80 border border-slate-900/80 p-5 rounded-2xl min-w-[220px] text-right flex flex-row md:flex-col justify-between items-baseline md:items-end w-full md:w-auto shadow-inner">
          <div>
            <p className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest">Lowest Scraped Price</p>
            <p className="text-3xl font-black text-neutral-50 tracking-tight mt-1 font-mono">
              {activeVariant && activeVariant.lowestPrice > 0 ? `₹${formatCurrency(activeVariant.lowestPrice)}` : 'N/A'}
            </p>
          </div>
          <p className="text-xs font-mono text-slate-400 mt-1.5 capitalize">on {activeVariant?.bestSource || 'Verified Resellers'}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 border-b border-slate-900">
        
        {/* Left Control Panel Column */}
        <div className="lg:col-span-5 p-6 sm:p-8 space-y-6 border-b lg:border-b-0 lg:border-r border-slate-900">
          
          {/* Flavor Chips Selector */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <label className="text-[11px] font-mono font-bold uppercase tracking-widest text-slate-500">
                1. Flavour Variation
              </label>
              <span className="text-[10px] font-mono text-slate-600">
                {selectedFlavor}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {distinctFlavors.map(flavor => {
                const isSelected = selectedFlavor === flavor;
                const hasCurrentSize = variants.some(v => v.flavor === flavor && v.weightDisplay === selectedSize);
                return (
                  <button
                    key={flavor}
                    onClick={() => handleFlavorSelect(flavor)}
                    className={`text-xs px-3.5 py-2 rounded-xl border transition-all cursor-pointer font-mono ${
                      isSelected
                        ? 'bg-neutral-50 text-slate-950 border-neutral-50 font-bold shadow-sm'
                        : hasCurrentSize
                        ? 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                        : 'bg-slate-950/60 text-slate-600 border-slate-900 hover:border-slate-800'
                    }`}
                  >
                    {flavor}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Sizing Container Chips Selector */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <label className="text-[11px] font-mono font-bold uppercase tracking-widest text-slate-500">
                2. Packaging Weight
              </label>
              <span className="text-[10px] font-mono text-slate-600">
                {activeVariant?.weightDisplay || selectedSize}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {distinctSizes.map(size => {
                const isOptionValid = availableSizesForCurrentFlavor.has(size);
                const isSelected = activeVariant?.weightDisplay === size || (selectedSize === size && isOptionValid);
                return (
                  <button
                    key={size}
                    disabled={!isOptionValid}
                    onClick={() => handleSizeSelect(size)}
                    className={`text-xs px-4 py-2 rounded-xl border transition-all font-mono ${
                      !isOptionValid
                        ? 'opacity-25 cursor-not-allowed border-slate-900 text-slate-700 bg-slate-950'
                        : isSelected
                        ? 'bg-neutral-50 text-slate-950 border-neutral-50 font-bold shadow-sm cursor-pointer'
                        : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700 cursor-pointer'
                    }`}
                  >
                    {size}
                  </button>
                );
              })}
            </div>
          </div>

          {/* User Watchlist Engine Execution Callouts */}
          <div className="flex flex-col gap-3 pt-4 border-t border-slate-900/60">
            <button
              onClick={() => setIsWatching(!isWatching)}
              className={`w-full h-12 rounded-xl text-xs font-mono font-bold tracking-wide border transition-all flex items-center justify-center gap-2 cursor-pointer ${
                isWatching
                  ? 'bg-slate-900 border-slate-800 text-emerald-400 font-extrabold'
                  : 'bg-slate-950 border-slate-800 text-slate-200 hover:border-slate-700'
              }`}
            >
              <Bell className="w-4 h-4" />
              {isWatching ? 'MONITORING FOR DISCOUNTS ✓' : 'SET PRICE DROP ALERT'}
            </button>
            
            <a
              href={activeVariant?.redirectUrl || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full h-12 bg-neutral-50 hover:bg-neutral-200 text-slate-950 text-xs font-mono font-black tracking-wide rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg cursor-pointer"
            >
              <span>REDIRECT TO MARKETPLACE</span>
              <ArrowUpRight className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Right Data Insights & Recharts Analytics Column */}
        <div className="lg:col-span-7 p-6 sm:p-8 bg-slate-950/40">
          <label className="text-[11px] font-mono font-bold uppercase tracking-widest text-slate-500 block mb-4">
            3. Historical Price Trajectory (90 Days)
          </label>
          
          <div className="w-full h-56 border border-slate-900 rounded-2xl bg-slate-950/80 p-4 shadow-inner">
            {activeVariant?.priceHistory && activeVariant.priceHistory.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activeVariant.priceHistory} margin={{ top: 10, right: 5, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="chartColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.25}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.3} />
                  <XAxis dataKey="date" stroke="#64748b" style={{ fontSize: '10px', fontFamily: 'monospace' }} tickLine={false} />
                  <YAxis stroke="#64748b" style={{ fontSize: '10px', fontFamily: 'monospace' }} domain={['dataMin - 200', 'dataMax + 200']} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#020617', borderColor: '#1e293b', borderRadius: '12px', fontFamily: 'monospace', fontSize: '11px' }}
                    itemStyle={{ color: '#f8fafc' }}
                    formatter={(val: any) => [`₹${formatCurrency(Number(val))}`, 'Sticker Price']}
                  />
                  <Area type="monotone" dataKey="price" name="Sticker Price" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#chartColor)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-center p-6 text-slate-500 font-mono text-xs">
                Awaiting scraper population history for this specific subset...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Advanced Analytics Drawer Footer */}
      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-900 bg-slate-950/60 p-6 sm:p-8">
        
        {/* Core Value Spec Matrix */}
        <div className="space-y-4 pb-6 md:pb-0 md:pr-6">
          <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-slate-400">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span>Analytical Yield Economics</span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="flex justify-between items-center py-2 border-b border-slate-900">
              <span className="text-slate-400">True Value Efficiency:</span>
              <span className="font-bold text-neutral-100">
                ₹{displayCostPer100g} / 100g pure protein
              </span>
            </div>

            <div className="flex justify-between items-center py-2 border-b border-slate-900">
              <span className="text-slate-400">Arbitrage Flavour Tax:</span>
              <span className={activeVariant && activeVariant.flavorTaxPct > 0 ? 'text-amber-500 font-bold' : 'text-slate-500'}>
                {displayFlavorTax}
              </span>
            </div>

            <div className="flex justify-between items-center py-2">
              <span className="text-slate-400">Bioavailability (DIAAS Metric):</span>
              <span className="font-bold text-neutral-100">
                {displayDiaas} Index Score
              </span>
            </div>
          </div>
        </div>

        {/* Reseller Distribution Metrics */}
        <div className="space-y-4 pt-6 md:pt-0 md:pl-6">
          <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest text-slate-400">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Aggregated Reseller Matrix</span>
          </div>

          {activeVariant?.offers && activeVariant.offers.length > 0 ? (
            <div className="divide-y divide-slate-900 font-mono text-xs">
              {activeVariant.offers.map((offer, idx) => (
                <div key={idx} className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-neutral-200 capitalize">{offer.seller}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      offer.isAvailable ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/50' : 'bg-rose-950/40 text-rose-400 border border-rose-900/50'
                    }`}>
                      {offer.isAvailable ? 'In Stock' : 'Out of Stock'}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-black text-neutral-100">₹{formatCurrency(offer.price)}</span>
                    <a
                      href={offer.url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-1 font-bold"
                    >
                      <span>Link</span>
                      <ArrowUpRight className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 font-mono text-xs py-4">
              No active stock links validated.
            </p>
          )}
        </div>

      </div>

    </div>
  );
}
