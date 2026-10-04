import React from 'react';
import Link from 'next/link';
import { ArrowLeft, CheckCircle2, AlertTriangle, ShieldCheck, ExternalLink } from 'lucide-react';
import { ProductListingView } from '@/types/masterSchema';
import { supabase } from '@/lib/supabase';
import { generateAffiliateUrl } from '@/utils/affiliate';

interface PageProps {
  searchParams: Promise<{ ids?: string; snapshotId?: string }>;
}

export default async function ComparePage({ searchParams }: PageProps) {
  const resolvedParams = await searchParams;
  const idsParam = resolvedParams.ids;
  const snapshotId = resolvedParams.snapshotId;

  let variantIds: string[] = [];

  if (snapshotId) {
    const { data: snapshot } = await supabase
      .from('comparison_snapshots')
      .select('variant_ids')
      .eq('id', snapshotId)
      .single();
    if (snapshot) variantIds = snapshot.variant_ids;
  } else if (idsParam) {
    variantIds = Array.from(new Set(idsParam.split(',').map((s) => s.trim()).filter(Boolean))).slice(0, 4);
  }

  if (variantIds.length < 2) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] text-[#111827] font-mono p-8 flex flex-col items-center justify-center">
        <h1 className="text-xl font-bold mb-4">INSUFFICIENT COMPARISON TARGETS</h1>
        <p className="text-xs text-[#6B7280] mb-6">Comparison requires selecting between 2 and 4 SKUs.</p>
        <Link href="/" className="border border-[#111827] bg-[#111827] text-white px-4 py-2 text-xs uppercase font-bold">
          ← Return to Terminal Screener
        </Link>
      </div>
    );
  }

  // Fetch comparison data directly
  const { data: variants } = await supabase
    .from('variants')
    .select(`
      id, sku_id, flavor, weight_grams, lowest_price_inr, best_value_metric, 
      raw_json_data, has_bot_reviews, authenticity_score,
      label_serving_size_g, label_protein_per_serving_g, calculated_purity_pct,
      products (
        id, brand, base_name, category_silo, protein_source, image_url,
        is_fairy_dusted, lab_verified, trust_score, fssai_warning_active
      ),
      price_listings (
        platform_name, source, price_inr, current_price_inr, source_url, 
        listing_url, in_stock, seller_name, is_authorized_seller
      )
    `)
    .in('id', variantIds);

  const items: ProductListingView[] = (variants || []).map((v: any) => {
    const prod = v.products || {};
    let rawAnalytics: any = {};
    try {
      if (typeof v.raw_json_data === 'string') rawAnalytics = JSON.parse(v.raw_json_data);
      else if (v.raw_json_data) rawAnalytics = v.raw_json_data;
    } catch {
      rawAnalytics = {};
    }

    const listings = v.price_listings || [];
    const inStockListings = listings.filter((l: any) => (l.in_stock ?? true) && Number(l.current_price_inr || l.price_inr || 0) > 0);
    const authorizedListings = inStockListings.filter((l: any) => l.is_authorized_seller ?? true);

    const bestOffer = authorizedListings.length
      ? authorizedListings.reduce((min: any, cur: any) =>
          Number(cur.current_price_inr || cur.price_inr) < Number(min.current_price_inr || min.price_inr) ? cur : min
        )
      : inStockListings.length
      ? inStockListings.reduce((min: any, cur: any) =>
          Number(cur.current_price_inr || cur.price_inr) < Number(min.current_price_inr || min.price_inr) ? cur : min
        )
      : null;

    const lowestPrice = bestOffer ? Number(bestOffer.current_price_inr || bestOffer.price_inr) : (Number(v.lowest_price_inr) || 0);
    const platformName = bestOffer?.platform_name || bestOffer?.source || 'Direct';
    const rawUrl = bestOffer?.source_url || bestOffer?.listing_url || '';
    const affiliateUrl = generateAffiliateUrl(rawUrl, platformName);

    const diaas = rawAnalytics?.analytics?.diaas_score || 1.0;
    const servingSize = Math.max(1.0, Number(v.label_serving_size_g) || 33.0);
    const proteinPerServing = Math.max(0.0, Number(v.label_protein_per_serving_g) || 24.0);
    const rawPurity = (proteinPerServing / servingSize) * 100;
    const purity = Math.min(100.0, Math.max(0.0, Number(v.calculated_purity_pct) || Number(rawPurity.toFixed(1))));
    const totalServings = Math.max(1, Number(v.weight_grams || 1000) / servingSize);
    const bioavailablePool = totalServings * (proteinPerServing * diaas);
    const fallbackCost = (bioavailablePool > 0 && lowestPrice > 0) ? Number((lowestPrice / bioavailablePool).toFixed(2)) : 0.0;
    const effectiveCost = Number(v.best_value_metric) || fallbackCost;

    return {
      productId: prod.id || '',
      variantId: v.id,
      brandName: prod.brand || 'Unknown',
      productName: prod.base_name || 'Protein',
      category: prod.category_silo || 'protein',
      weightGrams: Math.max(1, Number(v.weight_grams) || 1000),
      flavorName: v.flavor || 'Unflavored',
      purityPct: purity,
      diaasScore: diaas,
      effectiveCostPerBioavailableGram: effectiveCost,
      lowestPriceInr: lowestPrice,
      bestPlatform: platformName,
      isEasyDigest: Boolean(v.has_digestive_enzymes || v.is_lactose_free),
      hasFssaiWarning: prod.fssai_warning_active ?? false,
      ocrVerified: v.ocr_verified ?? false,
      trustScore: prod.trust_score ?? 100,
      authenticityScore: v.authenticity_score ?? 100,
      labVerified: prod.lab_verified ?? false,
      affiliateUrl,
    };
  });

  if (items.length < 2) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] text-[#111827] font-mono p-8 flex flex-col items-center justify-center">
        <h1 className="text-xl font-bold mb-4">INSUFFICIENT COMPARISON TARGETS</h1>
        <p className="text-xs text-[#6B7280] mb-6">Could not find at least 2 active variants for the provided IDs in the database.</p>
        <Link href="/" className="border border-[#111827] bg-[#111827] text-white px-4 py-2 text-xs uppercase font-bold">
          ← Return to Terminal Screener
        </Link>
      </div>
    );
  }

  const validCosts = items.map((i) => i.effectiveCostPerBioavailableGram).filter((c) => c > 0);
  const lowestEffectiveCost = validCosts.length ? Math.min(...validCosts) : 0;
  const maxCost = validCosts.length ? Math.max(...validCosts, 5.0) : 5.0;

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#111827] font-mono antialiased pb-20">
      {/* System Status Banner */}
      <div className="border-b border-[#E5E7EB] bg-white px-6 py-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-4">
          <Link href="/" className="font-bold flex items-center gap-1.5 hover:text-[#4B5563]">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>TERMINAL</span>
          </Link>
          <span className="text-[#9CA3AF]">/</span>
          <div className="font-bold tracking-tight">INDEX // CROSS-PRODUCT COMPARE MATRIX</div>
        </div>
        <div className="flex items-center gap-2 text-[#4B5563]">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>EQUALIZER ENGINE: ACTIVE</span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold uppercase tracking-tight text-[#111827]">
            Commodity Efficiency Matrix
          </h1>
          <p className="text-xs text-[#6B7280] mt-1">
            Standardized unit economics adjusted for DIAAS bioavailability and retail platform spreads.
          </p>
        </div>

        {/* Efficiency Chart */}
        <div className="bg-white border border-[#E5E7EB] p-5 mb-8">
          <div className="text-xs font-bold uppercase tracking-wider mb-4 text-[#374151]">
            Relative Cost Efficiency (₹ per Gram Bioavailable Protein)
          </div>
          <div className="space-y-3">
            {items.map((item) => {
              const pct = maxCost > 0 ? Math.min(100, Math.round((item.effectiveCostPerBioavailableGram / maxCost) * 100)) : 0;
              const isBest = item.effectiveCostPerBioavailableGram === lowestEffectiveCost;
              return (
                <div key={item.variantId} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-bold">
                      {item.brandName} - {item.productName} ({item.flavorName})
                    </span>
                    <span className={isBest ? "font-bold text-emerald-600" : "text-[#4B5563]"}>
                      ₹{item.effectiveCostPerBioavailableGram.toFixed(2)}/g
                      {isBest && " ★ BEST EFFICIENCY"}
                    </span>
                  </div>
                  <div className="w-full bg-[#E5E7EB] h-5 rounded-none overflow-hidden flex">
                    <div
                      className={`h-full ${isBest ? "bg-emerald-500" : "bg-[#111827]"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Tabular Matrix */}
        <div className="bg-white border border-[#E5E7EB] overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB] text-[#6B7280] uppercase text-[11px]">
                <th className="p-3.5 font-semibold w-48">Metric / Attribute</th>
                {items.map((item) => (
                  <th key={item.variantId} className="p-3.5 font-bold text-[#111827] min-w-[200px]">
                    <div>{item.brandName}</div>
                    <div className="text-[11px] text-[#4B5563] font-normal">{item.productName}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">₹/g Bioavailable Protein</td>
                {items.map((item) => {
                  const isBest = item.effectiveCostPerBioavailableGram === lowestEffectiveCost;
                  return (
                    <td key={item.variantId} className={`p-3.5 font-bold ${isBest ? "bg-emerald-50 text-emerald-700" : ""}`}>
                      ₹{item.effectiveCostPerBioavailableGram.toFixed(2)}/g
                      {isBest && <span className="ml-2 text-[10px] bg-emerald-600 text-white px-1.5 py-0.5">OPTIMAL</span>}
                    </td>
                  );
                })}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Lowest Active Price</td>
                {items.map((item) => (
                  <td key={item.variantId} className="p-3.5 font-bold">
                    ₹{item.lowestPriceInr.toLocaleString("en-IN")}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Purity %</td>
                {items.map((item) => (
                  <td key={item.variantId} className="p-3.5">
                    {item.purityPct.toFixed(1)}%
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">DIAAS Digestibility</td>
                {items.map((item) => (
                  <td key={item.variantId} className="p-3.5">
                    {item.diaasScore.toFixed(2)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Flavor & Weight</td>
                {items.map((item) => (
                  <td key={item.variantId} className="p-3.5">
                    {item.flavorName} • {item.weightGrams}g
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Trust Score</td>
                {items.map((item) => (
                  <td key={item.variantId} className="p-3.5">
                    <span className={(item.trustScore ?? 100) >= 85 ? "text-emerald-700 font-bold" : "text-amber-700 font-bold"}>
                      {item.trustScore ?? 100}/100
                    </span>
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Review Authenticity</td>
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
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Lab Verification</td>
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
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Best Fulfillment</td>
                {items.map((item) => (
                  <td key={item.variantId} className="p-3.5 capitalize">
                    {item.bestPlatform}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="p-3.5 font-bold bg-[#F9FAFB]">Direct Order Action</td>
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
    </div>
  );
}
