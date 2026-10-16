import React from "react";
import { SidebarSkeleton, CatalogGridSkeleton } from "@/components/catalog/CatalogSkeleton";

export default function CatalogLoading() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-32">
      {/* Header mock */}
      <div className="border-b border-slate-200 px-4 sm:px-6 py-3 bg-white">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="h-6 w-36 bg-slate-200 rounded-xs animate-pulse" />
          <div className="h-6 w-48 bg-slate-100 rounded-xs animate-pulse hidden md:block" />
        </div>
      </div>

      {/* Screener bar mock */}
      <div className="border-b border-slate-200 bg-white py-3 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
          <div className="h-8 w-64 bg-slate-100 rounded-xs animate-pulse" />
          <div className="h-8 w-32 bg-slate-100 rounded-xs animate-pulse" />
        </div>
      </div>

      {/* Main Content Skeleton */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <SidebarSkeleton />
          <div className="flex-1 min-w-0">
            <CatalogGridSkeleton count={6} />
          </div>
        </div>
      </main>
    </div>
  );
}
