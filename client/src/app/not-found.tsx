import React from "react";
import Link from "next/link";
import { ArrowLeft, Search, ShieldAlert } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-mono flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-sm p-8 shadow-xs">
        <div className="size-12 rounded-full bg-amber-50 border border-amber-200 text-amber-800 flex items-center justify-center mx-auto mb-4">
          <ShieldAlert className="size-6" />
        </div>
        <h1 className="text-xl font-black text-slate-900 uppercase tracking-tight mb-2">
          Page or SKU Not Found
        </h1>
        <p className="text-xs text-slate-600 mb-6 leading-relaxed">
          The requested product route, calculation, or comparison workspace does not exist or has been relocated to maintain verified catalog integrity.
        </p>

        <div className="flex flex-col gap-2">
          <Link
            href="/catalog"
            className="w-full py-2.5 px-4 bg-slate-900 hover:bg-emerald-800 text-white font-bold text-xs uppercase tracking-wider rounded-sm transition-colors flex items-center justify-center gap-1.5"
          >
            <Search className="size-3.5" />
            <span>Search Full Catalog</span>
          </Link>
          <Link
            href="/"
            className="w-full py-2.5 px-4 border border-slate-300 hover:border-slate-800 text-slate-700 hover:text-slate-900 font-bold text-xs uppercase tracking-wider rounded-sm transition-colors flex items-center justify-center gap-1.5"
          >
            <ArrowLeft className="size-3.5" />
            <span>Return to Home</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
