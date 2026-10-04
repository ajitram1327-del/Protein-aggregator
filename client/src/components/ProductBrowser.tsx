"use client";

import { useState, useMemo } from 'react';
import { ShoppingCart } from 'lucide-react';
import { ProductCard } from './catalog/ProductCard';
import { CatalogControls } from './catalog/CatalogControls';
import { FilterState, ProductItem } from './catalog/types';
import { CompareTray, CompareItem } from './CompareTray';

export interface DbPriceListing {
  source: string;
  price_inr: number;
  source_url: string;
  seller_name?: string;
  is_authorized_seller?: boolean;
}

export interface DbVariant {
  id: string;
  sku_id: string;
  flavor: string;
  weight_grams: number;
  lowest_price_inr: number;
  best_value_metric: number;
  label_serving_size_g?: number;
  label_protein_per_serving_g?: number;
  calculated_purity_pct?: number;
  raw_json_data: any;
  price_listings: DbPriceListing[];
  has_bot_reviews?: boolean;
  authenticity_score?: number;
}

export interface GroupedProduct {
  id: string;
  brand: string;
  baseProductName: string;
  categorySilo: string;
  proteinSource: string;
  imageUrl: string;
  variants: DbVariant[];
  lowestPrice: number;
  bestValueMetric: number;
  isFairyDusted?: boolean;
  labVerified?: boolean;
  trustScore?: number;
  labReportUrl?: string;
}

export function ProductBrowser({ initialProducts }: { initialProducts: GroupedProduct[] }) {
  // Filters mapped to the new CatalogControls state
  const [filters, setFilters] = useState<FilterState>({
    query: "",
    category: "",
    selectedBrands: [],
    maxPrice: 15000,
    verifiedOnly: false,
    sort: "featured",
  });
  const [isMobileFilterOpen, setIsMobileFilterOpen] = useState(false);

  // Modal
  const [selectedGroup, setSelectedGroup] = useState<GroupedProduct | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<DbVariant | null>(null);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [compareItems, setCompareItems] = useState<CompareItem[]>([]);

  const handleToggleCompare = (variant: DbVariant, group: GroupedProduct) => {
    setCompareItems((prev) => {
      const exists = prev.some((i) => i.variantId === variant.id);
      if (exists) {
        return prev.filter((i) => i.variantId !== variant.id);
      }
      if (prev.length >= 4) {
        alert("Compare tray limit is 4 items max.");
        return prev;
      }
      return [
        ...prev,
        {
          variantId: variant.id,
          brand: group.brand,
          productName: group.baseProductName,
          flavor: variant.flavor,
          weightGrams: variant.weight_grams,
          effectiveCost: variant.best_value_metric,
          lowestPrice: variant.lowest_price_inr,
        },
      ];
    });
  };

  const availableCategories = useMemo(() => Array.from(new Set(initialProducts.map(p => p.categorySilo).filter(Boolean))), [initialProducts]);
  const availableBrands = useMemo(() => Array.from(new Set(initialProducts.map(p => p.brand).filter(Boolean))), [initialProducts]);
  
  const maxPriceLimit = useMemo(() => {
    if (!initialProducts.length) return 5000;
    const prices = initialProducts.map(p => p.lowestPrice).filter(p => p !== Infinity);
    return prices.length ? Math.max(...prices) : 1000;
  }, [initialProducts]);

  const isLandingPage = !filters.query && !filters.category && filters.selectedBrands.length === 0 && filters.maxPrice === 15000 && !filters.verifiedOnly && filters.sort === "featured";

  const displayedGroups = useMemo(() => {
    return initialProducts
      .filter(g => {
        const queryLower = filters.query.toLowerCase().trim();
        const matchesQuery = !queryLower || `${g.baseProductName} ${g.brand}`.toLowerCase().includes(queryLower);
        const matchesCategory = !filters.category || g.categorySilo === filters.category;
        const matchesBrand = filters.selectedBrands.length === 0 || filters.selectedBrands.includes(g.brand);
        const matchesPrice = g.lowestPrice <= filters.maxPrice || g.lowestPrice === Infinity;
        const matchesVerified = !filters.verifiedOnly || !!g.labVerified;
        return matchesQuery && matchesCategory && matchesBrand && matchesPrice && matchesVerified;
      })
      .sort((a, b) => {
        if (filters.sort === "price-asc") return a.lowestPrice - b.lowestPrice;
        if (filters.sort === "price-desc") return b.lowestPrice - a.lowestPrice;
        return a.lowestPrice - b.lowestPrice; // featured defaults to price-asc
      });
  }, [initialProducts, filters]);

  const groupedVariants = useMemo(() => {
    if (!selectedGroup) return { groups: {}, flavorKeys: [] };
    const groups: Record<string, typeof selectedGroup.variants> = {};
    selectedGroup.variants?.forEach(v => {
      let cleanFlavor = v.flavor;
      cleanFlavor = cleanFlavor.replace(/\b\d+(?:\.\d+)?\s*(kg|g|gm|lbs|l|ml)\b/gi, '').trim();
      cleanFlavor = cleanFlavor.replace(/^[\/\-\|\,\s]+|[\/\-\|\,\s]+$/g, '').trim();
      if (!cleanFlavor || cleanFlavor.toLowerCase() === 'varies') cleanFlavor = 'Default';
      if (!groups[cleanFlavor]) groups[cleanFlavor] = [];
      groups[cleanFlavor].push(v);
    });
    return { groups, flavorKeys: Object.keys(groups) };
  }, [selectedGroup]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-32">
      <nav className="border-b border-[var(--card-border)] px-6 py-4 flex items-center justify-between sticky top-0 bg-white/95 backdrop-blur-xl z-40 shadow-sm">
        <div className="flex items-center justify-between w-full max-w-7xl mx-auto gap-8">
          <div className="font-black text-2xl tracking-tighter text-slate-800 italic cursor-pointer flex items-center" onClick={() => window.location.href='/'}>
            <span className="text-[var(--accent-green)]">PROTE</span>INDEX
          </div>
          <div className="flex items-center gap-4">
          </div>
        </div>
      </nav>

      {/* Main Layout using new UI structure */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        
        {isLandingPage ? (
          <div className="mb-16 flex flex-col w-full">
            
            {/* Hero Section */}
            <div className="relative w-full py-24 px-4 overflow-hidden flex flex-col items-center text-center">
              <div className="relative z-10 max-w-4xl w-full">
                <h1 className="text-4xl md:text-5xl font-black text-slate-900 leading-tight mb-8">
                  Track the real price of protein.
                </h1>
                
                {/* Omnibar */}
                <div className="relative max-w-2xl mx-auto w-full flex flex-col items-center bg-white rounded-2xl p-2 border border-slate-200 shadow-sm focus-within:border-emerald-500 transition-colors">
                  <div className="flex w-full items-center">
                    <div className="pl-4 pr-2 text-slate-400">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                    </div>
                    <input 
                      type="text" 
                      placeholder="Search whey, isolate, or specific brands..." 
                      className="flex-1 bg-transparent border-none outline-none text-slate-900 text-lg py-4 px-2 placeholder-slate-400"
                      onChange={(e) => setFilters(prev => ({...prev, query: e.target.value}))}
                    />
                  </div>
                  
                  {/* Omnibar Quick Tags */}
                  <div className="w-full flex flex-wrap gap-2 px-4 pb-3 pt-1 border-t border-slate-50 mt-2">
                    <span className="text-xs font-semibold text-slate-400 mt-1.5 mr-2">Quick:</span>
                    {["Whey Isolate", "Plant Protein", "Optimum Nutrition", "1kg", "2kg"].map(tag => (
                       <button 
                         key={tag}
                         onClick={() => setFilters(prev => ({...prev, query: tag}))}
                         className="px-3 py-1 bg-slate-50 border border-slate-200 rounded-full text-xs font-medium text-slate-600 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200 transition-colors"
                       >
                         {tag}
                       </button>
                    ))}
                  </div>
                </div>

                {/* Live Deals Ticker */}
                <div className="mt-8 flex items-center justify-center gap-3 text-sm font-medium text-emerald-700 bg-emerald-50/50 py-2 px-4 rounded-full border border-emerald-100 max-w-fit mx-auto">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  Live: As-It-Is ATOM Whey 1kg dropped ₹300 on Amazon
                </div>
              </div>
            </div>

            {/* Category Pills Section */}
            <div className="max-w-7xl mx-auto w-full px-4 mb-16 flex flex-col items-center">
              <div className="mb-8 text-center">
                <h3 className="text-3xl font-bold text-[#022539]">Explore our categories</h3>
              </div>
              
              <div className="flex flex-wrap justify-center gap-6">
                {availableCategories.map(cat => {
                  const categoryImageName = cat.toLowerCase().replace(/ /g, '_') + '.jpg';
                  return (
                    <button
                      key={cat}
                      onClick={() => setFilters(prev => ({...prev, category: cat}))}
                      className="flex items-center gap-4 pl-3 pr-8 py-2 rounded-full border bg-white border-[#E2E2E2] text-[#575757] font-semibold text-lg capitalize transition-all hover:bg-[#FFF3E0] hover:border-[#FB991C] hover:text-[#FB991C] hover:shadow-md hover:-translate-y-1"
                    >
                      <div className="w-12 h-12 shrink-0 rounded-full bg-[#F8F8F8] border border-[#E2E2E2] flex items-center justify-center overflow-hidden p-1">
                         <img 
                            src={`/categories/${categoryImageName}`} 
                            onError={(e) => { e.currentTarget.src = '/categories/protein.jpg'; }}
                            alt={cat} 
                            className="h-full w-full object-contain mix-blend-multiply" 
                         />
                      </div>
                      {cat.replace(/_/g, ' ')}
                    </button>
                  );
                })}
              </div>
            </div>

          </div>
        ) : (
          <div id="catalog-section" className="lg:grid lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-8 pt-4">
          <CatalogControls
            filters={filters}
            availableCategories={availableCategories}
            availableBrands={availableBrands}
            maxPriceLimit={maxPriceLimit}
            totalMatches={displayedGroups.length}
            isMobileFilterOpen={isMobileFilterOpen}
            onFilterChange={(partial) => setFilters(prev => ({ ...prev, ...partial }))}
            onResetFilters={() => setFilters({ query: "", category: "", selectedBrands: [], maxPrice: maxPriceLimit, verifiedOnly: false, sort: "featured" })}
            setIsMobileFilterOpen={setIsMobileFilterOpen}
          />

          <section className="mt-6 lg:mt-0">
            {displayedGroups.length === 0 ? (
              <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center">
                <p className="text-base font-semibold text-slate-800">
                  No products matched your criteria
                </p>
                <button
                  type="button"
                  onClick={() => setFilters({ query: "", category: "", selectedBrands: [], maxPrice: maxPriceLimit, verifiedOnly: false, sort: "featured" })}
                  className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
                >
                  Reset all filters
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
                {displayedGroups.map(product => {
                  const bestVariant = product.variants?.[0];
                  const productItem: ProductItem = {
                    id: product.id,
                    name: product.baseProductName,
                    brand: product.brand,
                    type: product.categorySilo,
                    price: product.lowestPrice === Infinity ? 0 : product.lowestPrice,
                    servingPrice: product.bestValueMetric === Infinity ? undefined : product.bestValueMetric,
                    proteinPerServing: bestVariant?.label_protein_per_serving_g,
                    servingSizeGrams: bestVariant?.label_serving_size_g,
                    purityPct: bestVariant?.calculated_purity_pct,
                    weightGrams: bestVariant?.weight_grams,
                    image: product.imageUrl,
                    isVerified: product.labVerified,
                    tag: product.isFairyDusted ? "Fairy Dusted" : undefined,
                  };
                  return (
                    <ProductCard 
                      key={product.id}
                      product={productItem}
                      onSelect={() => {
                        setSelectedGroup(product);
                        setSelectedVariant(product.variants?.[0] || null);
                        setActiveImageIndex(0);
                      }}
                    />
                  );
                })}
              </div>
            )}
          </section>
        </div>
        )}
      </main>

      {/* Product Modal (New Design) */}
      {selectedGroup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-6 bg-slate-900/40 backdrop-blur-sm transition-all">
          <div className="bg-white w-full h-full md:h-[90vh] md:max-w-6xl md:rounded-xl shadow-2xl relative flex flex-col md:flex-row overflow-hidden border border-slate-200">
            
            <button onClick={() => setSelectedGroup(null)} className="absolute top-4 right-4 bg-slate-100 hover:bg-slate-200 text-slate-800 w-10 h-10 rounded-full flex items-center justify-center font-bold z-50 transition-colors">×</button>

            {/* Left Image Area & Gallery */}
            {(() => {
               const images = [selectedGroup.imageUrl, selectedGroup.labReportUrl].filter(Boolean) as string[];
               return (
                <div className="w-full h-[40vh] md:h-full md:w-[45%] bg-white flex flex-col items-center p-6 border-b md:border-b-0 md:border-r border-slate-100 relative">
                  <div className="flex-1 w-full flex items-center justify-center relative min-h-[300px]">
                     {selectedGroup.labVerified && (
                        <div className="absolute top-0 left-0 bg-green-50 text-green-700 font-bold text-[10px] px-3 py-1 rounded-full border border-green-200 uppercase tracking-wide">
                          17% Off
                        </div>
                     )}
                     <div className="absolute top-0 right-0 p-1 bg-green-50 rounded text-green-700">
                       <div className="w-3 h-3 rounded-full bg-green-500"></div>
                     </div>
                     <img src={images[activeImageIndex] || "/placeholder.png"} alt={selectedGroup.baseProductName} className="w-4/5 max-h-[50vh] object-contain transition-all" />
                  </div>
                  
                  {/* Thumbnails */}
                  <div className="flex gap-2 mt-4 overflow-x-auto w-full justify-center px-4 py-2">
                    {images.map((img, idx) => (
                      <button 
                        key={idx}
                        onClick={() => setActiveImageIndex(idx)}
                        className={`w-16 h-16 rounded-xl border-2 flex items-center justify-center p-1 overflow-hidden transition-all shrink-0 ${activeImageIndex === idx ? 'border-yellow-400' : 'border-slate-200'}`}
                      >
                         <img src={img} className="w-full h-full object-contain" alt={`Thumbnail ${idx+1}`} />
                      </button>
                    ))}
                  </div>
                </div>
               );
            })()}

            {/* Right Details Area */}
            <div className="w-full md:w-[55%] p-6 md:p-8 overflow-y-auto bg-white flex flex-col gap-6">
              
              <div>
                <h1 className="text-xl md:text-2xl font-bold text-slate-900 leading-snug">{selectedGroup.baseProductName}</h1>
                <div className="mt-4 border-b border-slate-100 pb-4">
                  <div className="flex items-end gap-2">
                    <span className="text-3xl font-black font-mono tabular-nums text-slate-900">₹{selectedVariant?.lowest_price_inr || 'N/A'}</span>
                  </div>
                  
                  {/* True Cost Engine */}
                  {selectedVariant && selectedVariant.label_protein_per_serving_g && selectedVariant.label_serving_size_g && selectedVariant.weight_grams && (
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                      <span className="bg-emerald-50 border border-emerald-200 text-emerald-700 font-mono tabular-nums font-bold px-3 py-1.5 rounded text-sm">
                        ₹{(selectedVariant.lowest_price_inr / (selectedVariant.weight_grams * (selectedVariant.label_protein_per_serving_g / selectedVariant.label_serving_size_g))).toFixed(2)} / g pure protein
                      </span>
                      {selectedVariant.calculated_purity_pct && (
                         <span className="text-slate-500 font-mono tabular-nums">
                           {Math.round(selectedVariant.calculated_purity_pct)}% Purity
                         </span>
                      )}
                    </div>
                  )}
                  
                  <div className="mt-4 flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                    <span className="text-emerald-700 font-bold text-sm">In Stock Across {selectedVariant?.price_listings?.length || 1} Vendors</span>
                  </div>
                </div>
              </div>

              {/* Flavor / Colour Selection */}
              {(() => {
                 const { groups, flavorKeys } = groupedVariants;
                 
                 let activeFlavor = flavorKeys[0];
                 if (selectedVariant) {
                     let tempFlavor = selectedVariant.flavor;
                     tempFlavor = tempFlavor.replace(/\b\d+(?:\.\d+)?\s*(kg|g|gm|lbs|l|ml)\b/gi, '').trim();
                     tempFlavor = tempFlavor.replace(/^[\/\-\|\,\s]+|[\/\-\|\,\s]+$/g, '').trim();
                     if (!tempFlavor || tempFlavor.toLowerCase() === 'varies') tempFlavor = 'Default';
                     if (groups[tempFlavor]) activeFlavor = tempFlavor;
                 }

                 return (
                   <div className="flex flex-col gap-5 mt-2">
                     <div>
                       <div className="text-sm text-slate-500 mb-3">Flavour: <span className="font-semibold text-slate-900">{activeFlavor}</span></div>
                       <div className="flex flex-wrap gap-2">
                         {flavorKeys.map(fk => (
                            <button
                              key={fk}
                              onClick={() => setSelectedVariant(groups[fk][0])}
                              className={`px-4 py-2 text-[11px] font-semibold rounded-lg border transition-all ${
                                activeFlavor === fk 
                                  ? "border-orange-400 text-orange-600 bg-orange-50/30 shadow-sm" 
                                  : "border-slate-200 text-slate-600 bg-white hover:border-slate-300"
                              }`}
                            >
                              {fk}
                            </button>
                         ))}
                       </div>
                     </div>

                     <div>
                       <div className="text-sm text-slate-500 mb-3">Weight: <span className="font-semibold text-slate-900">{selectedVariant ? (selectedVariant.weight_grams >= 1000 ? `${+(selectedVariant.weight_grams / 1000).toFixed(2)} kg` : `${Math.round(selectedVariant.weight_grams)} gm`) : ''}</span></div>
                       <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                         {groups[activeFlavor]
                            ?.sort((a, b) => a.weight_grams - b.weight_grams)
                            .map(v => {
                            const active = selectedVariant?.id === v.id;
                            const weightStr = v.weight_grams >= 1000 ? `${+(v.weight_grams / 1000).toFixed(2)} Kg` : `${Math.round(v.weight_grams)} gm`;
                            const pricePer100g = Math.round((v.lowest_price_inr / v.weight_grams) * 100);
                            
                            return (
                              <div
                                key={v.id}
                                onClick={() => setSelectedVariant(v)}
                                className={`cursor-pointer p-3 rounded-lg border transition-all flex flex-col gap-1 relative ${
                                  active 
                                    ? "border-orange-400 shadow-[0_0_0_1px_rgba(251,146,60,1)] bg-white" 
                                    : "border-slate-200 bg-white hover:border-slate-300"
                                }`}
                              >
                                {v.weight_grams <= 50 && (
                                   <div className="absolute -top-2 left-2 bg-orange-100 text-orange-600 text-[9px] font-bold px-1.5 rounded-sm">Single Serve</div>
                                )}
                                <div className="text-xs text-slate-600 font-medium">{weightStr}</div>
                                <div className="flex items-baseline gap-1 mt-1">
                                  <span className="font-bold text-slate-900 text-lg">₹{v.lowest_price_inr}</span>
                                  <span className="text-[10px] text-slate-400">(₹{pricePer100g}/100 g)</span>
                                </div>
                              </div>
                            )
                         })}
                       </div>
                     </div>
                   </div>
                 )
              })()}
              
              {/* Multi-Vendor Buy Box */}
              <div className="mt-2 border-t border-slate-100 pt-6">
                <div className="text-sm font-semibold text-slate-900 mb-4">Active Market Arbitrage</div>
                <div className="flex flex-col gap-3">
                  {selectedVariant?.price_listings?.map((l, i) => (
                    <div key={l.source} className={`flex items-center justify-between p-4 rounded-xl border ${i === 0 ? 'border-emerald-200 bg-emerald-50/30' : 'border-slate-200 bg-white hover:bg-slate-50'}`}>
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-bold capitalize text-slate-900">{l.source}</span>
                        {i === 0 && <span className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider">Lowest Price</span>}
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-lg font-black font-mono tabular-nums text-slate-900">₹{l.price_inr}</span>
                        <a 
                          href={l.source_url} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${i === 0 ? 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                        >
                          View ↗
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

                {/* Compare Action Button */}
                {selectedVariant && selectedGroup && (
                  <div className="mt-4">
                    <button
                      onClick={() => handleToggleCompare(selectedVariant, selectedGroup)}
                      className={`w-full py-2.5 px-3 border font-mono text-xs uppercase font-bold tracking-wider transition-colors flex items-center justify-center gap-2 ${
                        compareItems.some(i => i.variantId === selectedVariant.id)
                          ? "bg-[#111827] text-white border-[#111827]"
                          : "bg-white text-[#111827] border-[#111827] hover:bg-[#F3F4F6]"
                      }`}
                    >
                      {compareItems.some(i => i.variantId === selectedVariant.id)
                        ? "✓ Added to Compare Tray (Remove)"
                        : "+ Add Variant to Compare Matrix"}
                    </button>
                  </div>
                )}

              {/* Details Section */}
              <div className="mt-4 border border-slate-100 rounded-xl bg-white shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-100">
                  <h3 className="font-bold text-slate-900 text-lg">Details</h3>
                </div>
                
                <div className="p-4">
                  {/* Stats Row */}
                  <div className="bg-slate-50 rounded-lg p-4 flex items-center justify-between text-center divide-x divide-slate-200 mb-6">
                    <div className="flex-1">
                      <div className="font-bold text-slate-900">25 g</div>
                      <div className="text-xs text-slate-500 mt-1">Protein / Serving</div>
                    </div>
                    <div className="flex-1">
                      <div className="font-bold text-slate-900">62.5 %</div>
                      <div className="text-xs text-slate-500 mt-1">Protein</div>
                    </div>
                    <div className="flex-1">
                      <div className="font-bold text-slate-900">
                        {selectedVariant ? Math.floor(selectedVariant.weight_grams / 40) : 25}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">Servings</div>
                    </div>
                  </div>

                  {/* Attributes List */}
                  <div className="flex flex-col gap-3 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Best Before</span>
                      <span className="text-slate-800 font-medium">July 2028</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Weight</span>
                      <span className="text-slate-800 font-medium">
                        {selectedVariant ? (selectedVariant.weight_grams >= 1000 ? `${+(selectedVariant.weight_grams / 1000).toFixed(2)} kg` : `${Math.round(selectedVariant.weight_grams)} gm`) : '1 kg'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Flavour</span>
                      <span className="text-slate-800 font-medium">{selectedVariant?.flavor || 'Rich Chocolate Creme'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Preference</span>
                      <span className="text-slate-800 font-medium">Vegetarian</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Serving Size</span>
                      <span className="text-slate-800 font-medium">40g</span>
                    </div>
                  </div>

                  <div className="mt-6 text-center">
                    <button className="text-xs font-bold text-slate-800 border border-slate-200 rounded-lg px-4 py-2 hover:bg-slate-50 transition-colors inline-flex items-center gap-1">
                      View More <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      )}

      {/* Floating Compare Tray (PRD Section 11.3) */}
      <CompareTray
        selectedItems={compareItems}
        onRemove={(id) => setCompareItems((prev) => prev.filter((i) => i.variantId !== id))}
        onClear={() => setCompareItems([])}
      />
    </div>
  );
}
