import React, { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft, Calculator, ShieldCheck } from "lucide-react";
import { TrueProteinCostCalculator } from "@/components/calculator/TrueProteinCostCalculator";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "True Protein Cost & Yield Calculator | Proteindex",
  description:
    "Calculate normalized cost per gram of pure protein, scoop yield, and price efficiency across Indian supplement brands.",
};

interface CalculatorPageProps {
  searchParams: Promise<{
    price?: string;
    weight?: string;
    protein?: string;
    serving?: string;
  }>;
}

async function CalculatorContent({ searchParams }: CalculatorPageProps) {
  const params = await searchParams;
  const initialPrice = params.price ? Number(params.price) : 3499;
  const initialWeight = params.weight ? Number(params.weight) : 1000;
  const initialProtein = params.protein ? Number(params.protein) : 80;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
      <div className="mb-6 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-500">
          <Link href="/catalog" className="hover:text-slate-900 flex items-center gap-1 font-semibold">
            <ArrowLeft className="size-3" /> Catalog
          </Link>
          <span>/</span>
          <span className="text-slate-900 font-bold">Protein Economic Calculator</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          <Calculator className="size-6 text-emerald-700" />
          <span>True Protein Cost & Yield Calculator</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 font-mono">
          Normalize packaging sticker price into pure bioavailable economics. Never pay for fillers, maltodextrin, or oversized scoops.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-sm p-4 sm:p-6 shadow-xs mb-8">
        <TrueProteinCostCalculator
          initialPrice={isFinite(initialPrice) && initialPrice > 0 ? initialPrice : 3499}
          initialWeight={isFinite(initialWeight) && initialWeight > 0 ? initialWeight : 1000}
          initialProteinPct={isFinite(initialProtein) && initialProtein > 0 ? initialProtein : 80}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-slate-600">
        <div className="p-4 bg-slate-100 rounded-sm border border-slate-200">
          <h2 className="font-bold text-slate-900 mb-1 flex items-center gap-1.5">
            <ShieldCheck className="size-4 text-emerald-700" />
            Why ₹/g Protein Matters
          </h2>
          <p className="leading-relaxed">
            A 1kg tub at ₹1,999 with 60% purity yields 600g pure protein (₹3.33/g). A 1kg tub at ₹2,499 with 85% purity yields 850g pure protein (₹2.94/g). The higher sticker price is actually 11% cheaper per gram of muscle-building protein.
          </p>
        </div>
        <div className="p-4 bg-slate-100 rounded-sm border border-slate-200">
          <h2 className="font-bold text-slate-900 mb-1">
            Category Baseline Standards
          </h2>
          <ul className="space-y-1">
            <li>• Whey Isolate: 85–93% Purity (Target ₹2.10–₹2.60/g)</li>
            <li>• Whey Concentrate: 70–80% Purity (Target ₹1.45–₹1.90/g)</li>
            <li>• Creatine Monohydrate: 100% Purity (Target ₹3.50–₹5.50/3g dose)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function CalculatorPage(props: CalculatorPageProps) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-24">
      {/* Navigation header */}
      <header className="border-b border-slate-200 px-4 sm:px-6 py-3 bg-white">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto">
          <Link href="/" className="font-black text-2xl tracking-tighter text-slate-900 italic flex items-center">
            <span className="text-emerald-700">PROTE</span>INDEX
          </Link>
          <div className="flex items-center gap-3 text-xs font-mono">
            <Link href="/catalog" className="text-slate-600 hover:text-slate-900 font-bold">
              Catalog Screener →
            </Link>
          </div>
        </div>
      </header>

      <Suspense fallback={<div className="max-w-4xl mx-auto p-12 text-center font-mono text-xs text-slate-400">Loading economic calculator...</div>}>
        <CalculatorContent {...props} />
      </Suspense>
    </div>
  );
}
