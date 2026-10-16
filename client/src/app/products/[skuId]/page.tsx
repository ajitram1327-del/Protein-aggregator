import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ShieldCheck, AlertCircle, Clock, ExternalLink, Check, Scale } from "lucide-react";
import { getProductBySkuOrId } from "@/lib/products";
import { formatInr, computeCategoryMetrics, indexedAgo } from "@/lib/analytics";
import { Metadata } from "next";

interface ProductPageProps {
  params: Promise<{ skuId: string }>;
  searchParams: Promise<{ variant?: string }>;
}

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  const { skuId } = await params;
  const product = await getProductBySkuOrId(skuId);

  if (!product) {
    return {
      title: "Product Not Found | Proteindex",
      description: "The requested supplement could not be found in our catalog.",
    };
  }

  return {
    title: `${product.brand} ${product.baseProductName} | True Price & Nutrition | Proteindex`,
    description: `Analyzed economics, verified nutrition facts, seller price comparison and lab verification status for ${product.brand} ${product.baseProductName}.`,
  };
}

export default async function ProductDetailPage({ params, searchParams }: ProductPageProps) {
  const { skuId } = await params;
  const resolvedSearchParams = await searchParams;
  const selectedVariantId = resolvedSearchParams.variant;

  const product = await getProductBySkuOrId(skuId);

  if (!product) {
    notFound();
  }

  // Active variant resolution
  const activeVariant =
    (selectedVariantId
      ? product.variants.find(
          (v) =>
            v.id.toLowerCase() === selectedVariantId.toLowerCase() ||
            v.sku_id.toLowerCase() === selectedVariantId.toLowerCase()
        )
      : null) || product.variants[0];

  const currentPrice = activeVariant?.lowest_price_inr || product.lowestPrice || 0;
  const rawServingSize = activeVariant?.label_serving_size_g ?? null;
  const rawProteinG = activeVariant?.label_protein_per_serving_g ?? null;
  const hasValidProtein =
    rawProteinG !== null &&
    rawServingSize !== null &&
    rawServingSize > 0 &&
    rawProteinG > 0 &&
    rawProteinG <= rawServingSize;

  const servingSize = hasValidProtein ? rawServingSize! : 0;
  const proteinG = hasValidProtein ? rawProteinG! : 0;
  const totalServings =
    hasValidProtein && servingSize > 0
      ? Math.max(1, Math.round((activeVariant?.weight_grams || 1000) / servingSize))
      : 0;

  const catMetrics = computeCategoryMetrics(
    product.categorySilo,
    currentPrice,
    activeVariant?.raw_json_data || (hasValidProtein ? {
      servingSizeGrams: servingSize,
      proteinPerServingGrams: proteinG,
      servingsPerContainer: totalServings,
      totalProteinPerTubGrams: proteinG * totalServings,
    } : {}),
    activeVariant?.weight_grams || 1000
  );

  const listings = activeVariant?.price_listings || [];
  const inStockOffers = listings.filter((l) => l.in_stock !== false && l.is_in_stock !== false);
  const isInStock = listings.length === 0 ? true : inStockOffers.length > 0;

  const freshestTime =
    listings.find((l) => l.scraped_at)?.scraped_at ||
    activeVariant?.last_observed_at ||
    product.lastObservedAt;

  const isCreatine = product.categorySilo.toLowerCase().includes("creatine");

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-24">
      {/* Top Breadcrumb Header */}
      <header className="border-b border-slate-200 px-4 sm:px-6 py-3 bg-white sticky top-0 z-30 shadow-xs">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="font-black text-2xl tracking-tighter text-slate-900 italic cursor-pointer flex items-center"
            >
              <span className="text-emerald-700">PROTE</span>INDEX
            </Link>
            <span className="text-slate-300">|</span>
            <div className="flex items-center gap-2 text-xs font-mono">
              <Link href="/catalog" className="text-slate-500 hover:text-slate-900 flex items-center gap-1 font-semibold">
                <ArrowLeft className="size-3" /> Catalog
              </Link>
              <span className="text-slate-300">/</span>
              <span className="text-slate-900 font-bold truncate max-w-[200px] sm:max-w-xs">
                {product.baseProductName}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href={`/compare?ids=${activeVariant?.id || product.id}`}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:border-slate-800 text-xs font-mono font-bold text-slate-700 rounded-sm shadow-xs transition-colors"
            >
              <Scale className="size-3.5 text-emerald-700" />
              <span>Compare</span>
            </Link>
            <Link
              href="/calculator"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 text-white hover:bg-emerald-800 text-xs font-mono font-bold uppercase rounded-sm transition-colors"
            >
              Calculator
            </Link>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Product Visual & Trust Overview */}
          <div className="lg:col-span-5 flex flex-col gap-6">
            <div className="bg-white border border-slate-200 rounded-sm p-8 flex items-center justify-center relative aspect-square shadow-xs">
              {/* Trust Badges */}
              <div className="absolute left-4 top-4 z-10 flex flex-col gap-1.5 items-start">
                {product.labVerified && (
                  <span className="inline-flex items-center gap-1 rounded-xs bg-emerald-700 px-2.5 py-1 text-xs font-mono font-bold uppercase text-white shadow-xs">
                    <ShieldCheck className="size-3.5" /> 3rd-Party Lab Verified
                  </span>
                )}
                {product.isFairyDusted && (
                  <span className="inline-flex items-center gap-1 rounded-xs bg-amber-600 px-2.5 py-1 text-xs font-mono font-bold uppercase text-white shadow-xs">
                    <AlertCircle className="size-3.5" /> Filler / Amino Warning
                  </span>
                )}
              </div>

              {product.imageUrl ? (
                <img
                  src={product.imageUrl}
                  alt={product.baseProductName}
                  className="max-h-80 w-auto object-contain mix-blend-multiply"
                />
              ) : (
                <div className="text-sm font-mono text-slate-400">No Image Available</div>
              )}
            </div>

            {/* Verification & Trust Spec */}
            <div className="bg-white border border-slate-200 rounded-sm p-5 font-mono text-xs shadow-xs">
              <h2 className="font-bold text-slate-900 uppercase tracking-wider text-xs mb-3 border-b border-slate-100 pb-2">
                Verification & Lab Evidence
              </h2>
              <div className="space-y-2.5 text-slate-700">
                <div className="flex justify-between">
                  <span className="text-slate-500">Audit Status:</span>
                  <span className="font-bold text-slate-900">
                    {product.labVerified ? "Independent NABL Certified" : "Declared Manufacturer Label"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Trust Score:</span>
                  <span className={`font-bold ${(product.trustScore ?? 100) >= 80 ? "text-emerald-700" : "text-amber-700"}`}>
                    {product.trustScore ?? 100} / 100
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Filler Detection:</span>
                  <span className={product.isFairyDusted ? "text-amber-700 font-bold" : "text-emerald-700 font-bold"}>
                    {product.isFairyDusted ? "Fillers Detected" : "Clean Ingredient Base ✓"}
                  </span>
                </div>
                {product.labReportUrl && (
                  <div className="pt-2 border-t border-slate-100 flex justify-between items-center">
                    <span className="text-slate-500">Certificate:</span>
                    <a
                      href={product.labReportUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-700 hover:underline font-bold flex items-center gap-1"
                    >
                      <span>View Public Lab Report</span>
                      <ExternalLink className="size-3" />
                    </a>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Economics, Variants, Nutrition & Offers */}
          <div className="lg:col-span-7 flex flex-col gap-6">
            {/* Identity & Dominant Economics */}
            <div className="bg-white border border-slate-200 rounded-sm p-6 shadow-xs">
              <div className="flex items-center justify-between text-xs font-mono uppercase tracking-wider text-slate-500 font-bold mb-1">
                <span className="text-emerald-700">{product.brand}</span>
                <span>{product.proteinSource || product.categorySilo.replace(/_/g, " ")}</span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight leading-snug">
                {product.baseProductName}
              </h1>

              {/* Dominant ₹/g Metric */}
              <div className="mt-4 p-4 bg-slate-50 border border-slate-200 rounded-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-bold block">
                    Equalized Primary Metric
                  </span>
                  <div className="flex items-baseline gap-2 mt-0.5">
                    {catMetrics.isPending ? (
                      <span className="text-sm font-mono font-bold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-xs">
                        Nutrition Pending Verification
                      </span>
                    ) : (
                      <>
                        <span className="text-3xl font-mono font-black text-emerald-800 tabular-nums">
                          {catMetrics.primaryValue}
                        </span>
                        <span className="text-xs font-mono font-bold text-slate-600">
                          {catMetrics.primaryLabel}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex flex-col sm:items-end">
                  <span className="text-[10px] font-mono text-slate-500 uppercase font-bold block">
                    Best Available Price
                  </span>
                  <span className="text-2xl font-mono font-black text-slate-900 tabular-nums">
                    {formatInr(currentPrice)}
                  </span>
                  <div className="flex items-center gap-1.5 text-[11px] font-mono mt-0.5">
                    <span className={`inline-block size-2 rounded-full ${isInStock ? "bg-emerald-600" : "bg-red-500"}`} />
                    <span className={isInStock ? "text-slate-700 font-semibold" : "text-red-600 font-bold"}>
                      {isInStock ? "In Stock" : "Out of Stock"}
                    </span>
                    {freshestTime && (
                      <span className="text-slate-400">· Checked {indexedAgo(freshestTime)}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Variant Selector */}
              <div className="mt-6">
                <span className="text-xs font-mono font-bold text-slate-700 uppercase tracking-wider block mb-2">
                  Select Pack Size & Flavour:
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {product.variants.map((v) => {
                    const isSelected = v.id === activeVariant?.id;
                    return (
                      <Link
                        key={v.id}
                        href={`/products/${product.id}?variant=${v.id}`}
                        className={`p-2.5 rounded-sm border text-left font-mono transition-colors ${
                          isSelected
                            ? "border-slate-900 bg-slate-900 text-white shadow-xs"
                            : "border-slate-200 bg-white text-slate-800 hover:border-slate-400"
                        }`}
                      >
                        <div className="text-xs font-bold truncate">{v.flavor}</div>
                        <div className="flex items-center justify-between text-[11px] mt-1 opacity-90">
                          <span>{v.weight_grams >= 1000 ? `${v.weight_grams / 1000}kg` : `${v.weight_grams}g`}</span>
                          <span className="font-bold">{formatInr(v.lowest_price_inr)}</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Nutrition Facts Panel */}
            <div className="bg-white border border-slate-200 rounded-sm p-6 shadow-xs font-mono text-xs">
              <h2 className="font-bold text-slate-900 uppercase tracking-wider text-xs mb-4 border-b border-slate-100 pb-2 flex items-center justify-between">
                <span>Quantitative Nutrition Specification</span>
                <span className="text-[10px] font-bold text-slate-500">
                  {hasValidProtein ? "AUDITED LABEL" : "PENDING AUDIT"}
                </span>
              </h2>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-sm">
                  <span className="text-slate-500 text-[10px] uppercase block">Scoop Size</span>
                  <span className="text-base font-bold text-slate-900 tabular-nums">
                    {hasValidProtein ? `${servingSize}g` : "—"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-sm">
                  <span className="text-slate-500 text-[10px] uppercase block">Protein / Scoop</span>
                  <span className="text-base font-bold text-emerald-800 tabular-nums">
                    {hasValidProtein ? `${proteinG}g` : "—"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-sm">
                  <span className="text-slate-500 text-[10px] uppercase block">Protein Purity</span>
                  <span className="text-base font-bold text-slate-900 tabular-nums">
                    {hasValidProtein && servingSize > 0 ? `${Math.round((proteinG / servingSize) * 100)}%` : "—"}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-sm">
                  <span className="text-slate-500 text-[10px] uppercase block">Total Servings</span>
                  <span className="text-base font-bold text-slate-900 tabular-nums">
                    {totalServings > 0 ? totalServings : "—"}
                  </span>
                </div>
              </div>

              {!hasValidProtein && (
                <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-sm text-xs leading-relaxed">
                  Notice: Nutritional values for this SKU are currently in quarantine pending independent panel audit. Values are excluded from ranking calculations to prevent synthetic score inflation.
                </div>
              )}
            </div>

            {/* Seller & Retailer Price Comparison Table */}
            <div className="bg-white border border-slate-200 rounded-sm p-6 shadow-xs font-mono text-xs">
              <h2 className="font-bold text-slate-900 uppercase tracking-wider text-xs mb-4 border-b border-slate-100 pb-2 flex items-center justify-between">
                <span>Verified Retailer Offers ({listings.length})</span>
                <span className="text-[10px] text-slate-500 font-normal">Real-time marketplace index</span>
              </h2>

              {listings.length === 0 ? (
                <div className="p-6 text-center text-slate-500">
                  No direct seller listings found for this variant.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-500 text-[10px] uppercase">
                        <th className="py-2 px-3">Platform</th>
                        <th className="py-2 px-3">Seller</th>
                        <th className="py-2 px-3 text-right">Price</th>
                        <th className="py-2 px-3 text-center">Stock</th>
                        <th className="py-2 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {listings.map((l, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                          <td className="py-3 px-3 font-bold text-slate-900 capitalize">
                            {l.source || "Direct D2C"}
                          </td>
                          <td className="py-3 px-3 text-slate-600">
                            {l.seller_name || "Official Brand Store"}
                            {l.is_authorized_seller && (
                              <span className="ml-1 text-[9px] bg-emerald-50 text-emerald-700 px-1 py-0.5 rounded-xs font-bold border border-emerald-200">
                                AUTH
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-right font-black text-slate-900 tabular-nums">
                            {formatInr(l.price_inr)}
                          </td>
                          <td className="py-3 px-3 text-center">
                            {l.in_stock !== false && l.is_in_stock !== false ? (
                              <span className="text-emerald-700 font-bold">In Stock</span>
                            ) : (
                              <span className="text-red-600 font-bold">Out of Stock</span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <a
                              href={l.source_url || "#"}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-1 bg-slate-900 hover:bg-emerald-800 text-white font-bold text-[11px] uppercase rounded-sm transition-colors"
                            >
                              <span>View Store</span>
                              <ExternalLink className="size-3" />
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
