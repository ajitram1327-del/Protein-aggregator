"use client";

import React from 'react';
import Link from 'next/link';
import { X, ArrowRight, BarChart2 } from 'lucide-react';

export interface CompareItem {
  variantId: string;
  brand: string;
  productName: string;
  flavor: string;
  weightGrams: number;
  effectiveCost?: number;
  lowestPrice?: number;
}

interface CompareTrayProps {
  selectedItems: CompareItem[];
  onRemove: (variantId: string) => void;
  onClear: () => void;
}

export function CompareTray({ selectedItems, onRemove, onClear }: CompareTrayProps) {
  if (selectedItems.length === 0) return null;

  const compareUrl = `/compare?ids=${selectedItems.map((i) => i.variantId).join(',')}`;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-[#111827] text-white border-t border-[#374151] px-4 py-3 font-mono shadow-xl">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-400">
            <BarChart2 className="w-4 h-4" />
            <span>COMPARE TRAY ({selectedItems.length}/4)</span>
          </div>
          <button
            onClick={onClear}
            className="text-[11px] text-gray-400 hover:text-white underline"
          >
            Clear all
          </button>
        </div>

        {/* Selected Slots Grid */}
        <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto py-1">
          {selectedItems.map((item) => (
            <div
              key={item.variantId}
              className="flex items-center gap-2 bg-[#1F2937] border border-[#374151] px-2.5 py-1.5 rounded-none text-xs min-w-[140px] max-w-[200px]"
            >
              <div className="truncate flex-1">
                <div className="font-bold truncate text-[11px] text-white">{item.brand}</div>
                <div className="truncate text-[10px] text-gray-400">
                  {item.flavor} ({item.weightGrams}g)
                </div>
              </div>
              <button
                onClick={() => onRemove(item.variantId)}
                className="text-gray-400 hover:text-red-400 p-0.5"
                title="Remove"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}

          {/* Empty slot placeholders */}
          {Array.from({ length: 4 - selectedItems.length }).map((_, idx) => (
            <div
              key={`empty-${idx}`}
              className="hidden md:flex items-center justify-center border border-dashed border-[#4B5563] text-[#6B7280] text-[10px] px-3 py-2 w-[120px]"
            >
              + Slot {selectedItems.length + idx + 1}
            </div>
          ))}
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-2">
          {selectedItems.length >= 2 ? (
            <Link
              href={compareUrl}
              className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-[#0A0A0A] font-bold px-4 py-2 text-xs uppercase tracking-wider rounded-none"
            >
              <span>Launch Matrix</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          ) : (
            <div className="text-[11px] text-gray-400">
              Select {2 - selectedItems.length} more to compare
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
