"use client";

import React from "react";

export function ProductCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="flex flex-col justify-between bg-white border border-slate-200 rounded-sm overflow-hidden h-[438px] max-w-full"
    >
      <div className="flex flex-col">
        {/* Image frame skeleton (176px / h-44) */}
        <div className="h-44 w-full bg-slate-100 motion-safe:animate-pulse p-4 border-b border-slate-100 flex items-center justify-center">
          <div className="w-24 h-24 bg-slate-200/80 rounded-sm" />
        </div>

        {/* Content area */}
        <div className="p-3.5 flex flex-col gap-2">
          {/* Brand & Silo */}
          <div className="flex justify-between items-center">
            <div className="h-3 w-16 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
            <div className="h-3 w-12 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
          </div>

          {/* Title 2-lines (h-9) */}
          <div className="flex flex-col gap-1.5 h-9 justify-center">
            <div className="h-3.5 w-full bg-slate-200 rounded-xs motion-safe:animate-pulse" />
            <div className="h-3.5 w-3/4 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
          </div>

          {/* Primary Equalized Metric */}
          <div className="flex items-baseline justify-between pt-1">
            <div className="h-6 w-28 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
            <div className="h-4 w-16 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
          </div>

          {/* Weight pills */}
          <div className="flex gap-1 mt-0.5">
            <div className="h-4 w-10 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
            <div className="h-4 w-10 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
          </div>

          {/* Macro pill */}
          <div className="h-6 w-full bg-slate-100 border border-slate-200/80 rounded-xs motion-safe:animate-pulse mt-0.5" />

          {/* Price & Freshness row */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
            <div className="h-5 w-20 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
            <div className="h-4 w-16 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
          </div>
        </div>
      </div>

      {/* Button footer */}
      <div className="p-3.5 pt-0">
        <div className="h-8 w-full bg-slate-900/10 rounded-sm motion-safe:animate-pulse" />
      </div>
    </div>
  );
}

export function SidebarSkeleton() {
  return (
    <aside
      aria-hidden="true"
      className="hidden lg:block w-[280px] shrink-0 border border-slate-200 bg-white rounded-sm p-4 font-mono space-y-5"
    >
      <div className="flex justify-between items-center border-b border-slate-100 pb-3">
        <div className="h-4 w-20 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
        <div className="h-3 w-12 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
      </div>

      <div className="space-y-2">
        <div className="h-3.5 w-24 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
        <div className="space-y-1.5 pl-1">
          <div className="h-4 w-full bg-slate-100 rounded-xs motion-safe:animate-pulse" />
          <div className="h-4 w-5/6 bg-slate-100 rounded-xs motion-safe:animate-pulse" />
          <div className="h-4 w-4/6 bg-slate-100 rounded-xs motion-safe:animate-pulse" />
        </div>
      </div>

      <div className="space-y-2">
        <div className="h-3.5 w-28 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
        <div className="h-6 w-full bg-slate-100 rounded-xs motion-safe:animate-pulse" />
      </div>

      <div className="space-y-2">
        <div className="h-3.5 w-20 bg-slate-200 rounded-xs motion-safe:animate-pulse" />
        <div className="space-y-1.5 pl-1">
          <div className="h-4 w-full bg-slate-100 rounded-xs motion-safe:animate-pulse" />
          <div className="h-4 w-3/4 bg-slate-100 rounded-xs motion-safe:animate-pulse" />
        </div>
      </div>
    </aside>
  );
}

export function CatalogGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, idx) => (
        <ProductCardSkeleton key={idx} />
      ))}
    </div>
  );
}

export function CompareTrayPlaceholder() {
  return (
    <div
      aria-hidden="true"
      className="h-[76px] sm:h-[88px] w-full pointer-events-none"
    />
  );
}
