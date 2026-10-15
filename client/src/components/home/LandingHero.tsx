"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Search,
  ArrowRight,
  ShieldCheck,
  TrendingDown,
  Layers,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Bell,
  Calculator,
} from "lucide-react";
import { GroupedProduct, CANONICAL_CATEGORIES } from "@/components/ProductBrowser";
import { formatInr, costPer100gProtein } from "@/lib/analytics";
import { LiveMarketPulse } from "@/components/common/LiveMarketPulse";
import { TrueProteinCostCalculator } from "@/components/calculator/TrueProteinCostCalculator";
import { PriceAlertModal } from "@/components/common/PriceAlertModal";

interface LandingHeroProps {
  initialProducts: GroupedProduct[];
}

export const LandingHero: React.FC<LandingHeroProps> = ({ initialProducts }) => {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [isAlertOpen, setIsAlertOpen] = useState(false);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/catalog?q=${encodeURIComponent(searchQuery.trim())}`);
    } else {
      router.push("/catalog");
    }
  };

  // Live Genuine Market Metrics
  const totalVariants = useMemo(() => {
    return initialProducts.reduce((acc, p) => acc + (p.variants?.length || 1), 0);
  }, [initialProducts]);

  const uniqueBrands = useMemo(() => {
    return Array.from(new Set(initialProducts.map((p) => p.brand).filter(Boolean)));
  }, [initialProducts]);

  const labVerifiedCount = useMemo(() => {
    return initialProducts.filter((p) => p.labVerified).length;
  }, [initialProducts]);

  // Curated Top Value Picks (Lowest ₹ / 100g Pure Protein)
  const topValuePicks = useMemo(() => {
    return initialProducts
      .slice()
      .sort((a, b) => {
        const getCost = (p: GroupedProduct) => {
          if (p.bestValueMetric && isFinite(p.bestValueMetric)) return p.bestValueMetric;
          const v0 = p.variants[0];
          const w = v0?.weight_grams || 1000;
          const s = v0?.label_serving_size_g || 33;
          const prot = v0?.label_protein_per_serving_g || 24;
          return costPer100gProtein(p.lowestPrice, Math.round(w / s), prot) || Infinity;
        };
        return getCost(a) - getCost(b);
      })
      .slice(0, 6);
  }, [initialProducts]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* 0. Live Drops Ticker Strip (Stitch Screen 1) */}
      <LiveMarketPulse onOpenAlertModal={() => setIsAlertOpen(true)} />

      {/* 1. Global Navigation Bar */}
      <header className="border-b border-slate-200 px-4 sm:px-8 py-3.5 sticky top-0 bg-white/95 backdrop-blur-md z-40 shadow-xs">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <Link
              href="/"
              className="font-black text-2xl tracking-tighter text-slate-900 italic flex items-center shrink-0"
            >
              <span className="text-emerald-700">PROTE</span>INDEX
              <span className="ml-2 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-xs bg-slate-100 text-slate-700 border border-slate-300 not-italic font-bold hidden sm:inline-block">
                IN Market
              </span>
            </Link>

            <nav className="hidden lg:flex items-center gap-5 text-xs font-mono font-semibold text-slate-600">
              <Link href="/catalog?category=protein" className="hover:text-slate-900 transition-colors">
                Whey & Plant
              </Link>
              <Link href="/catalog?category=creatine" className="hover:text-slate-900 transition-colors">
                Creatine
              </Link>
              <Link href="/catalog?category=pre_workout" className="hover:text-slate-900 transition-colors">
                Pre-Workout
              </Link>
              <Link href="/catalog?category=mass_gainer" className="hover:text-slate-900 transition-colors">
                Mass Gainers
              </Link>
              <a href="#calculator" className="hover:text-slate-900 transition-colors text-emerald-700 font-bold">
                Cost Calculator
              </a>
              <Link href="/compare" className="hover:text-slate-900 transition-colors text-slate-400">
                Compare Matrix
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsAlertOpen(true)}
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 hover:border-slate-800 text-slate-700 hover:text-slate-900 text-xs font-mono font-bold uppercase tracking-wider rounded-sm transition-colors"
            >
              <Bell className="size-3.5 text-emerald-600" />
              <span>Set Alert</span>
            </button>

            <Link
              href="/catalog"
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-900 hover:bg-emerald-800 text-white text-xs font-mono font-bold uppercase tracking-wider rounded-sm transition-colors shadow-xs"
            >
              <span>Explore Catalog</span>
              <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* 2. Hero Section (Nutrabay / Modern Clean Commerce Style) */}
      <section className="relative pt-12 pb-14 px-4 sm:px-6 max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-sm border border-emerald-300 bg-emerald-50 text-emerald-800 text-xs font-mono font-bold uppercase tracking-wider mb-5">
          Indian Supplement Market Intelligence · Pure Yield Screener
        </div>

        <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-slate-900 max-w-4xl mx-auto mb-4 leading-tight">
          Stop Overpaying For Supplement Filler.
        </h1>
        <p className="text-sm sm:text-base text-slate-600 max-w-2xl mx-auto mb-8 leading-relaxed">
          We scrape authorized Indian retailers in real-time, filter out counterfeit grey-market sellers, and normalize prices by{" "}
          <strong className="text-slate-900 font-bold">active-ingredient yield</strong> rather than arbitrary tub weights.
        </p>

        {/* Central High-Impact Search Box */}
        <form onSubmit={handleSearchSubmit} className="max-w-2xl mx-auto mb-4">
          <div className="relative flex items-center shadow-xs">
            <Search className="absolute left-4 size-5 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search whey isolate, creatine, brand (Nakpro, ON, MuscleBlaze)..."
              aria-label="Search all supplement listings"
              className="w-full pl-12 pr-28 py-3.5 text-sm font-mono border-2 border-slate-300 rounded-sm outline-none focus:border-slate-900 bg-white"
            />
            <button
              type="submit"
              className="absolute right-2 px-4 py-2 bg-slate-900 hover:bg-emerald-800 text-white font-mono text-xs font-bold uppercase tracking-wider rounded-xs transition-colors"
            >
              Search
            </button>
          </div>
        </form>

        {/* Quick Search Suggestion Pills */}
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs font-mono text-slate-500 mb-10">
          <span>Popular:</span>
          {[
            { label: "Whey Isolate", url: "/catalog?category=protein&q=isolate" },
            { label: "Creatine Monohydrate", url: "/catalog?category=creatine" },
            { label: "Raw Unflavored", url: "/catalog?q=unflavored" },
            { label: "Budget Beast < ₹250", url: "/catalog?q=budget" },
            { label: "Lab Verified", url: "/catalog?verified=true" },
          ].map((pill) => (
            <Link
              key={pill.label}
              href={pill.url}
              className="px-2.5 py-1 bg-white border border-slate-200 rounded-xs hover:border-slate-400 text-slate-700 transition-colors"
            >
              {pill.label}
            </Link>
          ))}
        </div>

        {/* Live Genuine Market Metrics Strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-4xl mx-auto mb-14 text-left font-mono">
          <div className="p-3.5 rounded-sm border border-slate-200 bg-white">
            <div className="text-[10px] text-slate-400 font-bold uppercase">TRACKED INSTRUMENTS</div>
            <div className="text-2xl font-bold text-slate-900 tabular-nums">
              {initialProducts.length} Products
            </div>
          </div>
          <div className="p-3.5 rounded-sm border border-slate-200 bg-white">
            <div className="text-[10px] text-slate-400 font-bold uppercase">TRACKED SKUS</div>
            <div className="text-2xl font-bold text-slate-900 tabular-nums">
              {totalVariants} Variants
            </div>
          </div>
          <div className="p-3.5 rounded-sm border border-slate-200 bg-white">
            <div className="text-[10px] text-slate-400 font-bold uppercase">VERIFIED BRANDS</div>
            <div className="text-2xl font-bold text-slate-900 tabular-nums">
              {uniqueBrands.length} Brands
            </div>
          </div>
          <div className="p-3.5 rounded-sm border border-slate-200 bg-white">
            <div className="text-[10px] text-slate-400 font-bold uppercase">LAB AUDITED</div>
            <div className="text-2xl font-bold text-emerald-700 tabular-nums">
              {labVerifiedCount} Audited
            </div>
          </div>
        </div>

        {/* 3. Category Gateway Grid */}
        <div className="text-left mb-4 flex items-center justify-between">
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500">
            Browse By Supplement Category:
          </h2>
          <Link href="/catalog" className="text-xs font-mono font-bold text-emerald-800 hover:underline">
            View All Categories →
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 text-left mb-16">
          {CANONICAL_CATEGORIES.map((cat) => (
            <Link
              key={cat.id}
              href={`/catalog?category=${cat.id}`}
              className="p-4 bg-white border border-slate-200 rounded-sm hover:border-slate-400 transition-colors flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-xs border ${cat.badgeTone}`}>
                    {cat.badge}
                  </span>
                  <ChevronRight className="size-4 text-slate-400 group-hover:text-emerald-700 transition-colors" />
                </div>
                <h3 className="font-bold text-slate-900 group-hover:text-emerald-800 transition-colors">
                  {cat.title}
                </h3>
                <p className="text-[11px] font-mono text-emerald-700 font-bold mt-0.5 mb-1.5">
                  {cat.tagline}
                </p>
                <p className="text-xs text-slate-600 line-clamp-2">
                  {cat.description}
                </p>
              </div>

              <div className="pt-2 mt-3 border-t border-slate-100 text-[11px] font-mono flex justify-between">
                <span className="text-slate-400">Bench:</span>
                <span className="font-bold text-slate-800">{cat.metricExample}</span>
              </div>
            </Link>
          ))}
        </div>

        {/* 4. Top Value Picks (Sneakopedia Minimal Card Grid - Image 4) */}
        <div className="text-left mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 font-mono">
              Top Value Instruments (Pure Protein Yield)
            </h2>
            <p className="text-xs font-mono text-slate-500">
              Ranked strictly by verified cost per 100g pure protein. No sponsored placement.
            </p>
          </div>
          <Link
            href="/catalog?sort=value-asc"
            className="text-xs font-mono font-bold text-emerald-800 hover:underline"
          >
            See Full Ranked Matrix →
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-left mb-16">
          {topValuePicks.map((product) => {
            const v0 = product.variants[0];
            const weightG = v0?.weight_grams || 1000;
            const sSize = v0?.label_serving_size_g || 33;
            const prot = v0?.label_protein_per_serving_g || 24;
            const servings = Math.max(1, Math.round(weightG / sSize));
            const cost100g = Math.round(costPer100gProtein(product.lowestPrice, servings, prot));

            return (
              <div
                key={product.id}
                className="bg-white border border-slate-200 rounded-sm hover:border-slate-400 transition-colors flex flex-col justify-between overflow-hidden"
              >
                <div>
                  {/* Image Frame */}
                  <div className="relative aspect-square w-full bg-slate-50 flex items-center justify-center p-4 border-b border-slate-100">
                    {product.labVerified && (
                      <span className="absolute top-2 left-2 px-1.5 py-0.5 bg-emerald-700 text-white text-[9px] font-mono font-bold uppercase rounded-xs">
                        LAB AUDITED
                      </span>
                    )}
                    {product.imageUrl ? (
                      <img
                        src={product.imageUrl}
                        alt={product.baseProductName}
                        className="max-h-full max-w-full object-contain mix-blend-multiply"
                      />
                    ) : (
                      <div className="text-xs font-mono text-slate-400">No Image</div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="p-4">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold mb-1">
                      {product.brand} · {product.categorySilo.replace(/_/g, " ")}
                    </div>
                    <h3 className="font-bold text-sm text-slate-900 line-clamp-2 h-[38px]">
                      {product.baseProductName}
                    </h3>

                    <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-baseline justify-between">
                      <div>
                        <span className="text-[10px] font-mono text-slate-400 block uppercase">
                          Starting from
                        </span>
                        <span className="text-lg font-mono font-black text-emerald-700 tabular-nums">
                          {formatInr(product.lowestPrice)}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-xs border border-emerald-300 bg-emerald-50 text-emerald-800">
                        ₹{cost100g} / 100g
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-4 pt-0">
                  <Link
                    href={`/catalog?q=${encodeURIComponent(product.brand)}`}
                    className="w-full py-2 bg-slate-900 hover:bg-emerald-800 text-white text-xs font-mono font-bold uppercase tracking-wider rounded-sm flex items-center justify-center gap-1 transition-colors"
                  >
                    <span>Inspect Stores</span>
                    <ArrowRight className="size-3" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>

        {/* 4.5 Interactive True Protein Cost Calculator (Stitch Screen 1 Utility) */}
        <div id="calculator" className="mb-14 scroll-mt-20">
          <TrueProteinCostCalculator />
        </div>

        {/* 5. Why ProteIndex Trust Pillars */}
        <div className="text-left mb-6">
          <h2 className="text-base font-bold text-slate-900 font-mono">
            How ProteIndex Analyzes Supplements
          </h2>
          <p className="text-xs font-mono text-slate-500">
            Engineered to remove retail marketing tricks, fairy dusting, and artificial flavor taxes.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left font-mono text-xs mb-16">
          <div className="p-5 bg-white border border-slate-200 rounded-sm">
            <div className="font-bold text-sm text-slate-900 mb-2 flex items-center gap-2">
              <span className="text-emerald-700">01.</span> True Active-Yield Math
            </div>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              Brands use 45g scoops loaded with maltodextrin to advertise &apos;cheap&apos; protein. We normalize every SKU strictly by cost per gram of authentic active protein.
            </p>
          </div>

          <div className="p-5 bg-white border border-slate-200 rounded-sm">
            <div className="font-bold text-sm text-slate-900 mb-2 flex items-center gap-2">
              <span className="text-emerald-700">02.</span> Counterfeit & Grey Market Filter
            </div>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              We differentiate certified brand distributors (Appario, Nutrabay Direct, Brand D2C) from suspicious unverified marketplace sellers with mandatory batch QR warnings.
            </p>
          </div>

          <div className="p-5 bg-white border border-slate-200 rounded-sm">
            <div className="font-bold text-sm text-slate-900 mb-2 flex items-center gap-2">
              <span className="text-emerald-700">03.</span> Flavor Tax Arbitrage
            </div>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              Flavored variants routinely cost ₹200–₹500 more for less actual protein. We calculate instant flavor tax savings so you can choose when unflavored is superior.
            </p>
          </div>
        </div>

        {/* 6. Bottom Screener CTA Banner */}
        <div className="p-8 sm:p-10 border border-slate-300 rounded-sm bg-slate-900 text-white text-center">
          <h2 className="text-2xl sm:text-3xl font-black font-mono tracking-tight mb-2">
            Launch The Full Supplement Terminal
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 font-mono max-w-xl mx-auto mb-6">
            Compare store offers, DIAAS bioavailability scores, and historical price drops across all verified Indian brands.
          </p>
          <Link
            href="/catalog"
            className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-mono text-xs font-bold uppercase tracking-wider rounded-sm transition-colors"
          >
            <span>Open Dedicated Catalog Screener</span>
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-8 px-4 text-center font-mono text-xs text-slate-500 bg-white">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <strong className="text-slate-900">PROTEINDEX</strong> · Supplement Price & Purity Intelligence
          </div>
          <div className="flex items-center gap-4">
            <Link href="/catalog" className="hover:underline">Catalog Screener</Link>
            <Link href="/compare" className="hover:underline">Compare Tray</Link>
            <Link href="/scraper" className="hover:underline">Data Pipeline</Link>
          </div>
          <div>© {new Date().getFullYear()} ProteIndex. Zero Sponsored Bias.</div>
        </div>
      </footer>

      {/* Price Alert Subscription Modal */}
      <PriceAlertModal
        isOpen={isAlertOpen}
        onClose={() => setIsAlertOpen(false)}
        products={initialProducts}
      />
    </div>
  );
};
