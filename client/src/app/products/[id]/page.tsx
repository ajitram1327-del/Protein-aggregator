import { notFound } from 'next/navigation';
import { createClient } from '@supabase/supabase-js';
import {
  ProductWorkspace,
  MasterProductData,
  HydratedVariant,
  HistoricalPricePoint,
  ResellerOffer
} from '@/components/ProductWorkspace';
import { getProductBySkuOrId } from '@/lib/products';

export type { HistoricalPricePoint, ResellerOffer, HydratedVariant, MasterProductData };

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  process.env.SUPABASE_URL ||
  'https://mock.supabase.co';

const supabaseKey =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  'mock-key';

const supabase = createClient(supabaseUrl, supabaseKey);

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // 1. Fetch Master Parent Shell Data
  const { data: masterProduct, error: masterError } = await supabase
    .from('master_products')
    .select('*')
    .eq('id', id)
    .single();

  if (masterProduct && !masterError) {
    // 2. Fetch all Child Variants 
    const { data: variants, error: variantError } = await supabase
      .from('product_variants')
      .select('*')
      .eq('master_product_id', id);

    if (!variantError && variants && variants.length > 0) {
      const variantIds = variants.map((v: any) => v.id);

      // 3. Parallel fetching for price listings and analytics log history
      const [listingsRes, historyRes] = await Promise.all([
        supabase.from('price_listings').select('*').in('variant_id', variantIds),
        supabase
          .from('price_history_logs')
          .select('*')
          .in('variant_id', variantIds)
          .order('logged_at', { ascending: true })
      ]);

      const listings: any[] = listingsRes.data || [];
      const historyLogs: any[] = historyRes.data || [];

      // 4. Calculate variant price matrices and isolate base flavors
      const processVariants: HydratedVariant[] = variants.map((v: any) => {
        const variantOffers = listings
          .filter((l: any) => l.variant_id === v.id)
          .sort((a: any, b: any) => a.current_price_inr - b.current_price_inr);

        const lowestPrice = variantOffers[0]?.current_price_inr || 0;
        const bestSource = variantOffers[0]?.retailer_name || 'Out of Stock';
        const redirectUrl = variantOffers[0]?.source_url || '#';

        const purityRatio = (masterProduct.purity_percentage || 80) / 100;
        const pureYield = (v.weight_grams || 1000) * (v.pack_count || 1) * purityRatio;
        const costPer100gPure = pureYield > 0 ? (lowestPrice / pureYield) * 100 : 0;

        const variantHistory: HistoricalPricePoint[] = historyLogs
          .filter((h: any) => h.variant_id === v.id)
          .map((h: any) => ({
            date: new Date(h.logged_at).toLocaleDateString('en-IN', {
              month: 'short',
              day: 'numeric'
            }),
            price: Number(h.price_inr)
          }));

        return {
          id: v.id,
          flavor: v.flavor_name || 'Unflavored',
          weightDisplay: `${((v.weight_grams || 1000) / 1000).toFixed(1)} kg`,
          packCount: v.pack_count || 1,
          lowestPrice,
          bestSource,
          redirectUrl,
          costPer100gPure: Math.round(costPer100gPure * 10) / 10,
          offers: variantOffers.map((o: any) => ({
            seller: o.retailer_name,
            price: o.current_price_inr,
            url: o.source_url,
            isAvailable: o.is_in_stock
          })),
          priceHistory: variantHistory,
          flavorTaxPct: 0
        };
      });

      const validPrices = processVariants
        .filter(v => v.lowestPrice > 0)
        .map(v => v.lowestPrice);
      const baseFlavorCost = validPrices.length > 0 ? Math.min(...validPrices) : 0;

      const finalizedVariants = processVariants.map(v => ({
        ...v,
        flavorTaxPct:
          baseFlavorCost > 0 && v.lowestPrice > baseFlavorCost
            ? Math.round(((v.lowestPrice - baseFlavorCost) / baseFlavorCost) * 100 * 10) / 10
            : 0
      }));

      const productPayload: MasterProductData = {
        id: masterProduct.id,
        brand: masterProduct.brand_name || 'Generic',
        lineName: masterProduct.product_line || masterProduct.name || 'Protein Matrix',
        categorySilo: masterProduct.category_silo || 'protein',
        specs: {
          purity: `${masterProduct.purity_percentage || 80}%`,
          isSpiked: Boolean(masterProduct.is_amino_spiked),
          diaasScore: Number(masterProduct.diaas_score || 1.15)
        },
        variants: finalizedVariants
      };

      return (
        <main className="min-h-screen bg-slate-950 text-slate-100 py-12 px-4 sm:px-6 lg:px-8 selection:bg-emerald-500/30">
          <ProductWorkspace data={productPayload} />
        </main>
      );
    }
  }

  // Fallback: Resolve via canonical product catalog (e.g. from `/catalog`)
  const canonicalProduct = await getProductBySkuOrId(id);
  if (!canonicalProduct) return notFound();

  // Query real price tracking history for variants
  const variantIds = canonicalProduct.variants.map(v => v.id);
  const { data: realPriceHistory } = await supabase
    .from('price_history')
    .select('price_inr, recorded_at, offers!inner(variant_id)')
    .in('offers.variant_id', variantIds)
    .order('recorded_at', { ascending: true });

  const fallbackVariants: HydratedVariant[] = canonicalProduct.variants.map(v => {
    const purityRatio = 0.8;
    const pureYield = (v.weight_grams || 1000) * purityRatio;
    const costPer100gPure = pureYield > 0 ? ((v.lowest_price_inr || 0) / pureYield) * 100 : 0;

    // Build real price history series for this variant
    const vLogs = (realPriceHistory || [])
      .filter((h: any) => h.offers?.variant_id === v.id)
      .map((h: any) => ({
        date: new Date(h.recorded_at).toLocaleDateString('en-IN', {
          month: 'short',
          day: 'numeric'
        }),
        price: Number(h.price_inr)
      }));

    const priceHistory = vLogs.length > 0 
      ? vLogs 
      : [
          { date: 'Initial', price: v.lowest_price_inr || 2000 },
          { date: 'Current', price: v.lowest_price_inr || 2000 }
        ];

    return {
      id: v.id,
      flavor: v.flavor || 'Unflavored',
      weightDisplay: `${((v.weight_grams || 1000) / 1000).toFixed(1)} kg`,
      packCount: 1,
      lowestPrice: v.lowest_price_inr || 0,
      bestSource: v.price_listings?.[0]?.source || 'Direct',
      redirectUrl: v.price_listings?.[0]?.source_url || '#',
      costPer100gPure: Math.round(costPer100gPure * 10) / 10,
      offers: (v.price_listings || []).map(o => ({
        seller: o.source,
        price: o.price_inr,
        url: o.source_url,
        isAvailable: o.is_in_stock !== false
      })),
      priceHistory,
      flavorTaxPct: 0
    };
  });

  const validPrices = fallbackVariants
    .filter(v => v.lowestPrice > 0)
    .map(v => v.lowestPrice);
  const baseCost = validPrices.length > 0 ? Math.min(...validPrices) : 0;

  const finalizedFallback = fallbackVariants.map(v => ({
    ...v,
    flavorTaxPct:
      baseCost > 0 && v.lowestPrice > baseCost
        ? Math.round(((v.lowestPrice - baseCost) / baseCost) * 100 * 10) / 10
        : 0
  }));

  const fallbackPayload: MasterProductData = {
    id: canonicalProduct.id,
    brand: canonicalProduct.brand,
    lineName: canonicalProduct.baseProductName,
    categorySilo: canonicalProduct.categorySilo,
    specs: {
      purity: canonicalProduct.variants[0]?.calculated_purity_pct
        ? `${canonicalProduct.variants[0].calculated_purity_pct}%`
        : '80%',
      isSpiked: Boolean(canonicalProduct.aminoSpikeRisk),
      diaasScore: 1.15
    },
    variants: finalizedFallback
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 py-12 px-4 sm:px-6 lg:px-8 selection:bg-emerald-500/30">
      <ProductWorkspace data={fallbackPayload} />
    </main>
  );
}
