"use client";

import React, { useState } from "react";
import { AlertTriangle, ShieldCheck, ExternalLink, Sparkles, SlidersHorizontal } from "lucide-react";
import { ProductListingView } from "@/types/masterSchema";

interface CompareTableProps {
  items: ProductListingView[];
  lowestEffectiveCost: number;
}

export default function CompareTable({ items, lowestEffectiveCost }: CompareTableProps) {
  const [highlightDifferences, setHighlightDifferences] = useState(false);

  // Helper to check if a row has differing values across items
  const hasDifference = (extractor: (item: ProductListingView) => any) => {
    if (items.length <= 1) return false;
    const firstVal = JSON.stringify(extractor(items[0]));
    return items.some((item) => JSON.stringify(extractor(item)) !== firstVal);
  };

  const getRowClass = (differs: boolean) => {
    if (!highlightDifferences) return "";
    return differs ? "bg-amber-50/70 transition-colors" : "opacity-90";
  };

  return (
    <div className="space-y-4">
      {/* Table Toolbar & Difference Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white border border-[#E5E7EB] px-4 py-3 text-xs font-mono">
        <div className="flex items-center gap-2 text-[#4B5563]">
          <SlidersHorizontal className="w-3.5 h-3.5" />
          <span className="font-bold uppercase tracking-wider text-[#111827]">Comparison Matrix</span>
          <span className="text-[#9CA3AF]">({items.length} SKUs selected)</span>
        </div>

        <button
          onClick={() => setHighlightDifferences(!highlightDifferences)}
          className={`inline-flex items-center gap-2 px-3 py-1.5 text-xs font-bold uppercase transition-colors border ${
            highlightDifferences
              ? "bg-[#111827] text-white border-[#111827]"
              : "bg-white text-[#374151] border-[#D1D5DB] hover:bg-[#F3F4F6]"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{highlightDifferences ? "Highlighting Differences" : "Highlight Differences"}</span>
        </button>
      </div>

      {/* Overflow Container with Sticky Mobile Column & Sticky Header */}
      <div className="bg-white border border-[#E5E7EB] overflow-x-auto relative shadow-sm max-h-[75vh] overflow-y-auto">
        <table className="w-full text-left text-xs border-collapse font-mono">
          <thead className="sticky top-0 z-30 bg-white border-b border-[#E5E7EB] shadow-sm">
            <tr className="bg-[#F9FAFB] text-[#6B7280] uppercase text-[11px]">
              <th className="p-3.5 font-semibold w-52 min-w-[200px] sticky left-0 z-40 bg-[#F9FAFB] border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Metric / Attribute
              </th>
              {items.map((item) => (
                <th key={item.variantId} className="p-3.5 font-bold text-[#111827] min-w-[220px]">
                  <div className="text-xs text-[#111827] uppercase tracking-tight">{item.brandName}</div>
                  <div className="text-[11px] text-[#4B5563] font-normal truncate max-w-[200px]">{item.productName}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB]">
            {/* ₹/100g Pure Protein */}
            <tr className={getRowClass(hasDifference((i) => i.costPer100gProtein))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                ₹/100g Pure Protein
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5 font-bold">
                  {item.costPer100gProtein !== null && item.costPer100gProtein !== undefined
                    ? `₹${Math.round(item.costPer100gProtein).toLocaleString("en-IN")}`
                    : "Pending"}
                </td>
              ))}
            </tr>

            {/* ₹/g Bioavailable Protein */}
            <tr className={getRowClass(hasDifference((i) => i.effectiveCostPerBioavailableGram))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                ₹/g Bioavailable Protein
              </td>
              {items.map((item) => {
                const hasVal = item.effectiveCostPerBioavailableGram !== null && item.effectiveCostPerBioavailableGram !== undefined;
                const isBest = hasVal && item.effectiveCostPerBioavailableGram === lowestEffectiveCost;
                return (
                  <td key={item.variantId} className={`p-3.5 font-bold ${isBest ? "bg-emerald-50 text-emerald-700" : ""}`}>
                    {hasVal ? `₹${item.effectiveCostPerBioavailableGram!.toFixed(2)}/g` : "Pending audit"}
                    {isBest && <span className="ml-2 text-[10px] bg-emerald-600 text-white px-1.5 py-0.5">OPTIMAL</span>}
                  </td>
                );
              })}
            </tr>

            {/* Macro Breakdown Bar */}
            <tr className={getRowClass(hasDifference((i) => `${i.proteinPerServingGrams}-${i.carbsPerServingGrams}-${i.fatPerServingGrams}`))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Macro Breakdown Bar
              </td>
              {items.map((item) => {
                const prot = item.proteinPerServingGrams || 0;
                const carbs = item.carbsPerServingGrams || 0;
                const fat = item.fatPerServingGrams || 0;
                const total = Math.max(1, prot + carbs + fat);
                const protPct = Math.round((prot / total) * 100);
                const carbsPct = Math.round((carbs / total) * 100);
                const fatPct = Math.max(0, 100 - protPct - carbsPct);

                if (prot === 0 && carbs === 0 && fat === 0) {
                  return (
                    <td key={item.variantId} className="p-3.5 text-[#9CA3AF]">
                      Pending verification
                    </td>
                  );
                }

                return (
                  <td key={item.variantId} className="p-3.5 space-y-1.5">
                    <div className="flex h-3 w-full overflow-hidden bg-gray-100 rounded-none border border-gray-200">
                      <div style={{ width: `${protPct}%` }} className="bg-emerald-500" title={`Protein: ${prot}g (${protPct}%)`} />
                      <div style={{ width: `${carbsPct}%` }} className="bg-amber-400" title={`Carbs: ${carbs}g (${carbsPct}%)`} />
                      <div style={{ width: `${fatPct}%` }} className="bg-rose-400" title={`Fat: ${fat}g (${fatPct}%)`} />
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-[#4B5563]">
                      <span className="text-emerald-700 font-semibold">{prot}g P</span>
                      <span className="text-amber-700">{carbs}g C</span>
                      <span className="text-rose-700">{fat}g F</span>
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Lowest Active Price */}
            <tr className={getRowClass(hasDifference((i) => i.lowestPriceInr))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Lowest Active Price
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5 font-bold">
                  ₹{item.lowestPriceInr.toLocaleString("en-IN")}
                </td>
              ))}
            </tr>

            {/* Purity % */}
            <tr className={getRowClass(hasDifference((i) => i.purityPct))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Purity %
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  {item.purityPct !== null && item.purityPct !== undefined
                    ? `${item.purityPct.toFixed(1)}%`
                    : "Pending audit"}
                </td>
              ))}
            </tr>

            {/* DIAAS Digestibility */}
            <tr className={getRowClass(hasDifference((i) => i.diaasScore))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                DIAAS Digestibility
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  {item.diaasScore !== null && item.diaasScore !== undefined
                    ? item.diaasScore.toFixed(2)
                    : "Not available"}
                </td>
              ))}
            </tr>

            {/* Flavor & Weight */}
            <tr className={getRowClass(hasDifference((i) => `${i.flavorName}-${i.weightGrams}`))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Flavor & Weight
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  {item.flavorName} • {item.weightGrams}g
                </td>
              ))}
            </tr>

            {/* Trust Score */}
            <tr className={getRowClass(hasDifference((i) => i.trustScore))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Trust Score
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  <span className={(item.trustScore ?? 100) >= 85 ? "text-emerald-700 font-bold" : "text-amber-700 font-bold"}>
                    {item.trustScore ?? 100}/100
                  </span>
                </td>
              ))}
            </tr>

            {/* Review Authenticity */}
            <tr className={getRowClass(hasDifference((i) => i.authenticityScore))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Review Authenticity
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  {(item.authenticityScore ?? 100) >= 60 ? (
                    <span className="text-emerald-700 font-bold">LEGIT ({item.authenticityScore}%)</span>
                  ) : (
                    <span className="text-red-600 font-bold flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" /> HIGH BOT RISK
                    </span>
                  )}
                </td>
              ))}
            </tr>

            {/* Fairy Dusting Flag */}
            <tr className={getRowClass(hasDifference((i) => i.fairyDusted))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Fairy Dusting Flag
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  {item.fairyDusted ? (
                    <span className="text-amber-700 font-bold bg-amber-50 border border-amber-300 px-1.5 py-0.5 text-[10px]">
                      FILLER DETECTED
                    </span>
                  ) : (
                    <span className="text-emerald-700 font-bold">CLEAN ORDER ✓</span>
                  )}
                </td>
              ))}
            </tr>

            {/* Lab Verification */}
            <tr className={getRowClass(hasDifference((i) => i.labVerified))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Lab Verification
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  {item.labVerified ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-bold">
                      <ShieldCheck className="w-4 h-4" /> 3rd-Party PASS
                    </span>
                  ) : (
                    <span className="text-[#9CA3AF]">Unverified</span>
                  )}
                </td>
              ))}
            </tr>

            {/* Best Fulfillment */}
            <tr className={getRowClass(hasDifference((i) => i.bestPlatform))}>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Best Fulfillment
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5 capitalize">
                  {item.bestPlatform}
                </td>
              ))}
            </tr>

            {/* Direct Order Action */}
            <tr>
              <td className="p-3.5 font-bold bg-[#F9FAFB] sticky left-0 z-20 border-r border-[#E5E7EB] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">
                Direct Order Action
              </td>
              {items.map((item) => (
                <td key={item.variantId} className="p-3.5">
                  <a
                    href={item.affiliateUrl || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 bg-[#111827] hover:bg-black text-white px-3 py-1.5 font-bold text-xs uppercase"
                  >
                    <span>Buy via {item.bestPlatform}</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
