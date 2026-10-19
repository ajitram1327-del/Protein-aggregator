import type { Metadata } from 'next';
import Link from 'next/link';
import { Dumbbell, Layers, Calculator, Bell } from 'lucide-react';
import '@/app/globals.css';

export const metadata: Metadata = {
  title: {
    default: "ProteIndex — Supplement Price & Purity Intelligence Terminal",
    template: "%s | ProteIndex",
  },
  description: "Pure active-ingredient yield normalization engine and real-time supplement price tracking.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://proteindex.in"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased bg-[#fafafa] font-sans selection:bg-emerald-500/20">
      <body className="min-h-full flex flex-col text-slate-900 bg-[#fafafa]">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-slate-900 focus:text-white focus:text-xs focus:font-mono focus:font-bold"
        >
          Skip to content
        </a>

        {/* Universal Top Header Frame */}
        <header className="bg-white border-b border-slate-200/80 sticky top-0 z-50 shadow-xs">
          <div className="max-w-7xl mx-auto h-16 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white font-black text-sm group-hover:scale-105 transition-transform">
                P
              </div>
              <span className="font-mono font-black tracking-tighter text-sm uppercase text-slate-900">
                PROTE<span className="text-emerald-600">INDEX</span>
              </span>
            </Link>

            {/* Consolidated Route Action Group */}
            <nav className="flex items-center gap-1 sm:gap-2">
              <Link
                href="/catalog"
                className="text-xs font-bold text-slate-600 hover:text-slate-900 px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors flex items-center gap-1.5"
              >
                <Layers className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Browse Supplements</span>
                <span className="sm:hidden">Browse</span>
              </Link>
              <Link
                href="/compare"
                className="text-xs font-bold text-slate-600 hover:text-slate-900 px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors flex items-center gap-1.5"
              >
                <Dumbbell className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Compare Stores</span>
                <span className="sm:hidden">Compare</span>
              </Link>
              <Link
                href="/calculator"
                className="text-xs font-bold text-slate-600 hover:text-slate-900 px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors flex items-center gap-1.5"
              >
                <Calculator className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Protein Value Calculator</span>
                <span className="sm:hidden">Calculator</span>
              </Link>
              <Link
                href="/alerts"
                className="text-xs font-bold text-slate-600 hover:text-slate-900 px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors flex items-center gap-1.5"
              >
                <Bell className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Price Alerts</span>
              </Link>
            </nav>
          </div>
        </header>

        <div id="main-content" className="flex-1">
          {children}
        </div>
      </body>
    </html>
  );
}
