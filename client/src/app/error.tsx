"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCcw } from "lucide-react";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log unexpected errors
    console.error("Proteindex Route Exception:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-mono flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-sm p-8 shadow-xs">
        <div className="size-12 rounded-full bg-red-50 border border-red-200 text-red-700 flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="size-6" />
        </div>
        <h1 className="text-xl font-black text-slate-900 uppercase tracking-tight mb-2">
          Workspace Error
        </h1>
        <p className="text-xs text-slate-600 mb-6 leading-relaxed">
          An unexpected error occurred while compiling analytical metrics or fetching retailer listings.
        </p>

        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => reset()}
            className="w-full py-2.5 px-4 bg-slate-900 hover:bg-emerald-800 text-white font-bold text-xs uppercase tracking-wider rounded-sm transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <RefreshCcw className="size-3.5" />
            <span>Retry Calculation</span>
          </button>
          <Link
            href="/catalog"
            className="w-full py-2.5 px-4 border border-slate-300 hover:border-slate-800 text-slate-700 hover:text-slate-900 font-bold text-xs uppercase tracking-wider rounded-sm transition-colors text-center"
          >
            Return to Catalog
          </Link>
        </div>
      </div>
    </div>
  );
}
