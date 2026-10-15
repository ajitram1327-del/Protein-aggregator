"use client";

import React, { useState, useMemo } from "react";
import { Calculator, TrendingDown, TrendingUp, CheckCircle, Info, Sparkles, Scale } from "lucide-react";
import { formatInr } from "@/lib/analytics";

interface TrueProteinCostCalculatorProps {
  initialPrice?: number;
  initialWeight?: number;
  initialProteinPct?: number;
}

export const TrueProteinCostCalculator: React.FC<TrueProteinCostCalculatorProps> = ({
  initialPrice = 4149,
  initialWeight = 2000,
  initialProteinPct = 80,
}) => {
  const [weightGrams, setWeightGrams] = useState<number>(initialWeight);
  const [proteinPct, setProteinPct] = useState<number>(initialProteinPct);
  const [priceInr, setPriceInr] = useState<number>(initialPrice);
  const [servingSizeG, setServingSizeG] = useState<number>(30);
  const [proteinPerServingG, setProteinPerServingG] = useState<number>(24);
  const [inputMode, setInputMode] = useState<"percentage" | "label">("percentage");

  // Synchronize modes
  const effectivePct = useMemo(() => {
    if (inputMode === "percentage") {
      return Math.min(100, Math.max(1, proteinPct));
    }
    const s = Math.max(1, servingSizeG);
    const p = Math.max(0, proteinPerServingG);
    return Math.min(100, Math.round((p / s) * 100));
  }, [inputMode, proteinPct, servingSizeG, proteinPerServingG]);

  // Pure protein yield
  const yieldPureProteinG = useMemo(() => {
    const w = Math.max(1, weightGrams);
    return Math.round(w * (effectivePct / 100));
  }, [weightGrams, effectivePct]);

  // Cost per gram of pure protein
  const costPerGram = useMemo(() => {
    if (yieldPureProteinG <= 0) return 0;
    return priceInr / yieldPureProteinG;
  }, [priceInr, yieldPureProteinG]);

  const costPer100g = costPerGram * 100;
  const costPer24gScoop = costPerGram * 24;

  // Indian Market Benchmarks
  const isolateBenchmark = 2.42; // ₹2.42 / g pure protein
  const concentrateBenchmark = 1.58; // ₹1.58 / g pure protein

  const deltaVsIsolate = useMemo(() => {
    if (costPerGram <= 0) return 0;
    return ((costPerGram - isolateBenchmark) / isolateBenchmark) * 100;
  }, [costPerGram]);

  // Total servings & monthly budget
  const servingsInTub = useMemo(() => {
    const s = Math.max(1, servingSizeG);
    return Math.round(weightGrams / s);
  }, [weightGrams, servingSizeG]);

  const monthlyBudget1Scoop = (priceInr / Math.max(1, servingsInTub)) * 30;
  const monthlyBudget2Scoops = (priceInr / Math.max(1, servingsInTub)) * 60;

  // Benchmark progress bar percentage (0 to 100)
  const benchmarkBarPct = useMemo(() => {
    // 1.2 to 3.5 range
    const clamped = Math.min(3.5, Math.max(1.0, costPerGram));
    return Math.round(((3.5 - clamped) / (3.5 - 1.0)) * 100);
  }, [costPerGram]);

  return (
    <div className="w-full bg-white border border-slate-200 rounded-sm shadow-xs overflow-hidden font-sans">
      {/* Header */}
      <div className="bg-slate-50 border-b border-slate-200 p-4 sm:p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-emerald-800 text-xs font-mono font-bold uppercase tracking-wider">
            <Calculator className="size-3.5" />
            <span>Quantitative Pricing Utility</span>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mt-0.5">
            True Protein Cost & Yield Calculator
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Input any retail listing or gym offer to calculate the exact cost per gram of pure protein.
          </p>
        </div>

        {/* Input Mode Toggle */}
        <div className="flex items-center bg-slate-200/80 p-0.5 rounded-xs text-xs font-mono font-semibold">
          <button
            type="button"
            onClick={() => setInputMode("percentage")}
            className={`px-2.5 py-1 rounded-xs transition-colors ${
              inputMode === "percentage"
                ? "bg-white text-slate-900 shadow-xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            By Protein %
          </button>
          <button
            type="button"
            onClick={() => setInputMode("label")}
            className={`px-2.5 py-1 rounded-xs transition-colors ${
              inputMode === "label"
                ? "bg-white text-slate-900 shadow-xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            By Scoop Label
          </button>
        </div>
      </div>

      {/* Main Grid: Inputs & Output Readout */}
      <div className="p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Inputs (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Tub Weight */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-mono font-bold text-slate-700 uppercase">
                Net Tub Weight
              </label>
              <div className="flex gap-1">
                {[1000, 2000, 2270, 4540].map((w) => (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setWeightGrams(w)}
                    className={`px-1.5 py-0.5 text-[10px] font-mono font-semibold rounded-xs border transition-colors ${
                      weightGrams === w
                        ? "bg-slate-900 border-slate-900 text-white"
                        : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    {w === 2270 ? "5lb (2.27kg)" : w === 4540 ? "10lb" : `${w / 1000}kg`}
                  </button>
                ))}
              </div>
            </div>
            <div className="relative flex items-center">
              <input
                type="number"
                min={100}
                max={25000}
                step={50}
                value={weightGrams}
                onChange={(e) => setWeightGrams(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-300 rounded-xs px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:outline-none focus:border-slate-800"
              />
              <span className="absolute right-3 text-xs font-mono text-slate-400">grams</span>
            </div>
          </div>

          {/* Protein Concentration Inputs */}
          {inputMode === "percentage" ? (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-mono font-bold text-slate-700 uppercase">
                  Protein Purity / Concentration
                </label>
                <div className="flex gap-1">
                  {[70, 75, 80, 90].map((pct) => (
                    <button
                      key={pct}
                      type="button"
                      onClick={() => setProteinPct(pct)}
                      className={`px-1.5 py-0.5 text-[10px] font-mono font-semibold rounded-xs border transition-colors ${
                        proteinPct === pct
                          ? "bg-slate-900 border-slate-900 text-white"
                          : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      {pct}%
                    </button>
                  ))}
                </div>
              </div>
              <div className="relative flex items-center">
                <input
                  type="number"
                  min={10}
                  max={100}
                  step={1}
                  value={proteinPct}
                  onChange={(e) => setProteinPct(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xs px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:outline-none focus:border-slate-800"
                />
                <span className="absolute right-3 text-xs font-mono text-slate-400">%</span>
              </div>
              <span className="text-[11px] text-slate-500 font-mono mt-1 block">
                Standard whey concentrate is ~75%, whey isolate is 80–90%, raw is ~80%.
              </span>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-mono font-bold text-slate-700 uppercase block mb-1">
                  Serving / Scoop Size (g)
                </label>
                <input
                  type="number"
                  min={10}
                  max={250}
                  value={servingSizeG}
                  onChange={(e) => setServingSizeG(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xs px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:outline-none focus:border-slate-800"
                />
              </div>
              <div>
                <label className="text-xs font-mono font-bold text-slate-700 uppercase block mb-1">
                  Protein Per Scoop (g)
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={proteinPerServingG}
                  onChange={(e) => setProteinPerServingG(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xs px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:outline-none focus:border-slate-800"
                />
              </div>
            </div>
          )}

          {/* Current Price Quote */}
          <div>
            <label className="text-xs font-mono font-bold text-slate-700 uppercase block mb-1.5">
              Current Landed Price
            </label>
            <div className="relative flex items-center">
              <span className="absolute left-3 text-sm font-mono text-slate-500 font-bold">₹</span>
              <input
                type="number"
                min={100}
                max={50000}
                step={50}
                value={priceInr}
                onChange={(e) => setPriceInr(Number(e.target.value))}
                className="w-full bg-slate-50 border border-slate-300 rounded-xs pl-7 pr-3 py-2 text-sm font-mono font-bold text-slate-900 focus:outline-none focus:border-slate-800"
              />
            </div>
            <span className="text-[11px] text-slate-500 font-mono mt-1 block">
              Inclusive of shipping and coupon discounts.
            </span>
          </div>
        </div>

        {/* Right Output Readout Panel (5 cols) */}
        <div className="lg:col-span-5 bg-slate-50 border border-slate-200 rounded-sm p-4 sm:p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-slate-500 font-bold pb-2 border-b border-slate-200">
              <span>Calculated Net Value</span>
              <span className="text-emerald-700 font-bold">{effectivePct}% Pure</span>
            </div>

            {/* Big Headline Metric */}
            <div className="mt-3">
              <div className="text-[11px] font-mono text-slate-500 uppercase">Cost Per 100g Pure Protein</div>
              <div className="text-3xl font-mono font-black tabular-nums text-emerald-800 tracking-tight">
                {formatInr(costPer100g)}
                <span className="text-xs text-slate-500 font-normal ml-1">/ 100g</span>
              </div>
            </div>

            {/* Secondary Breakdown */}
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="bg-white p-2.5 rounded-xs border border-slate-200">
                <span className="text-slate-400 block text-[10px] uppercase">₹ / Gram</span>
                <span className="font-bold text-slate-900 text-sm">₹{costPerGram.toFixed(2)}/g</span>
              </div>
              <div className="bg-white p-2.5 rounded-xs border border-slate-200">
                <span className="text-slate-400 block text-[10px] uppercase">Per 24g Scoop</span>
                <span className="font-bold text-slate-900 text-sm">₹{costPer24gScoop.toFixed(1)}</span>
              </div>
            </div>

            {/* Benchmark Comparison & Progress */}
            <div className="mt-4 pt-3 border-t border-slate-200 space-y-2">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-600 font-medium">Vs. Isolate Benchmark (₹2.42/g):</span>
                <span
                  className={`font-bold ${
                    deltaVsIsolate <= 0 ? "text-emerald-700" : "text-amber-700"
                  }`}
                >
                  {deltaVsIsolate <= 0 ? (
                    <span className="inline-flex items-center gap-0.5">
                      <TrendingDown className="size-3" />
                      {Math.abs(deltaVsIsolate).toFixed(1)}% Under
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-0.5">
                      <TrendingUp className="size-3" />
                      +{deltaVsIsolate.toFixed(1)}% Premium
                    </span>
                  )}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    deltaVsIsolate <= 0 ? "bg-emerald-600" : "bg-amber-600"
                  }`}
                  style={{ width: `${Math.min(100, Math.max(10, benchmarkBarPct))}%` }}
                />
              </div>

              <div className="flex justify-between text-[10px] font-mono text-slate-400">
                <span>Total Clean Yield: {yieldPureProteinG}g</span>
                <span>{servingsInTub} Servings total</span>
              </div>
            </div>
          </div>

          {/* Monthly Budget Projections */}
          <div className="pt-3 border-t border-slate-200 text-xs font-mono space-y-1.5 bg-white p-3 rounded-xs border border-slate-200">
            <div className="text-[10px] uppercase font-bold text-slate-400">Projected Monthly Expense</div>
            <div className="flex justify-between text-slate-700">
              <span>1 Scoop/Day (30 scoops):</span>
              <span className="font-bold text-slate-900">{formatInr(monthlyBudget1Scoop)}</span>
            </div>
            <div className="flex justify-between text-slate-700">
              <span>2 Scoops/Day (60 scoops):</span>
              <span className="font-bold text-slate-900">{formatInr(monthlyBudget2Scoops)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
