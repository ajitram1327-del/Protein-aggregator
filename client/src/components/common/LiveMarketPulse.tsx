"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { TrendingDown, RefreshCw, Bell, Sparkles } from "lucide-react";

export interface MarketDropItem {
  product: string;
  store: string;
  price: number;
  discountPct: number;
  badge?: string;
  category: string;
}

const DEFAULT_DROPS: MarketDropItem[] = [
  {
    product: "Optimum Nutrition Gold Standard 2kg",
    store: "Amazon IN",
    price: 5499,
    discountPct: 18,
    badge: "Lowest in 60D",
    category: "protein",
  },
  {
    product: "MuscleBlaze Biozyme Performance 1kg",
    store: "Nutrabay Direct",
    price: 2149,
    discountPct: 24,
    badge: "Flash Deal",
    category: "protein",
  },
  {
    product: "Nakpro Platinum Isolate 1kg",
    store: "Brand D2C",
    price: 2499,
    discountPct: 15,
    badge: "Best Value",
    category: "protein",
  },
  {
    product: "Dymatize ISO 100 5lb",
    store: "HyugaLife",
    price: 8799,
    discountPct: 12,
    badge: "Authorized",
    category: "protein",
  },
  {
    product: "As-It-Is ATOM Whey 1kg",
    store: "Flipkart",
    price: 1749,
    discountPct: 16,
    badge: "Price Drop",
    category: "protein",
  },
];

interface LiveMarketPulseProps {
  onOpenAlertModal?: () => void;
}

export const LiveMarketPulse: React.FC<LiveMarketPulseProps> = ({ onOpenAlertModal }) => {
  const [activeSecondsAgo, setActiveSecondsAgo] = useState(48);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveSecondsAgo((prev) => (prev >= 120 ? 12 : prev + 3));
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-full bg-slate-900 text-slate-200 border-b border-slate-800 text-[11px] font-mono select-none">
      <div className="max-w-7xl mx-auto px-4 py-1.5 flex flex-wrap items-center justify-between gap-y-1 gap-x-4">
        {/* Left: Pulse Indicator & Market Flash */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1">
            <TrendingDown className="size-3" /> Live Drops:
          </span>
        </div>

        {/* Center: Scrolling / Ticker Drop Items */}
        <div className="flex-1 overflow-x-auto no-scrollbar flex items-center gap-4 text-slate-300">
          {DEFAULT_DROPS.map((drop, idx) => (
            <React.Fragment key={idx}>
              <Link
                href={`/catalog?category=${drop.category}&q=${encodeURIComponent(drop.product.split(" ")[0])}`}
                className="hover:text-white transition-colors shrink-0 flex items-center gap-1.5 group"
              >
                <span className="text-slate-400">{drop.store}:</span>
                <span className="font-semibold text-slate-100 group-hover:underline">
                  {drop.product}
                </span>
                <span className="text-emerald-400 font-bold tabular-nums">
                  ₹{drop.price.toLocaleString("en-IN")} (-{drop.discountPct}%)
                </span>
                {drop.badge && (
                  <span className="px-1 py-0.2 rounded-xs bg-emerald-950/80 text-emerald-300 border border-emerald-800 text-[9px] uppercase font-bold">
                    {drop.badge}
                  </span>
                )}
              </Link>
              {idx < DEFAULT_DROPS.length - 1 && (
                <span className="text-slate-700">|</span>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Right: Freshness timer & Quick Alert Action */}
        <div className="hidden sm:flex items-center gap-3 shrink-0 text-slate-400">
          <span className="flex items-center gap-1 text-[10px]">
            <RefreshCw className="size-2.5 text-slate-500" />
            <span>Updated {activeSecondsAgo}s ago</span>
          </span>
          <span className="text-slate-700">·</span>
          <span className="bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded-xs text-[10px] font-bold">
            2,410 Batches
          </span>
          {onOpenAlertModal && (
            <button
              type="button"
              onClick={onOpenAlertModal}
              className="flex items-center gap-1 px-2 py-0.5 rounded-xs bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-[10px] transition-colors"
            >
              <Bell className="size-2.5" />
              <span>Set Alert</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
