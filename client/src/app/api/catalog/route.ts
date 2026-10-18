import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabaseAdmin';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const rawCategory = searchParams.get('category') || 'all';

  // Strict Bidirectional Token Map
  const mapping: Record<string, string> = {
    protein: 'protein',
    'whey_&_plant_protein': 'protein',
    whey_protein: 'protein',
    whey: 'protein',
    creatine: 'creatine',
    creatine_monohydrate: 'creatine',
    'creatine monohydrate': 'creatine',
    pre_workout: 'pre_workout',
    'pre-workout_&_pump': 'pre_workout',
    preworkout: 'pre_workout',
    'pre-workout': 'pre_workout',
    mass_gainer: 'mass_gainers',
    mass_gainers: 'mass_gainers',
    gainers: 'mass_gainers',
    gainer: 'mass_gainers',
    'mass gainers': 'mass_gainers',
    snacks: 'snacks',
    snack: 'snacks',
    protein_snacks: 'snacks',
    'protein_snacks_&_bars': 'snacks',
  };

  const targetSilo = mapping[rawCategory.toLowerCase().trim()] || (rawCategory === 'all' ? 'all' : rawCategory.toLowerCase().trim());

  try {
    // Build multi-table join query safely on the server side using supabaseAdmin (Service Role)
    let query = supabaseAdmin
      .from('products')
      .select(`
        *,
        variants (
          *,
          price_listings (*)
        )
      `)
      .order('id', { ascending: true });

    if (targetSilo !== 'all') {
      query = query.eq('category_silo', targetSilo);
    }

    const { data: dbProducts, error } = await query;
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });

    // Format metrics cleanly before transmission
    const processData = (dbProducts || []).map((prod: any) => {
      const purityRatio = Number(prod.purity_percentage || 0) / 100;

      const processedVariants = (prod.variants || []).map((v: any) => {
        const liveOffers = (v.price_listings || [])
          .filter((l: any) => l.in_stock || l.is_in_stock)
          .sort((a: any, b: any) => (a.price_inr || a.current_price_inr || 0) - (b.price_inr || b.current_price_inr || 0));

        const bestPrice = liveOffers?.[0]?.price_inr || liveOffers?.[0]?.current_price_inr || v.lowest_price_inr || 0;
        const totalPureGrams = (v.weight_grams || 1000) * purityRatio;
        const costPer100gPure = totalPureGrams > 0 ? (bestPrice / totalPureGrams) * 100 : 0;

        return {
          id: v.id,
          sku_id: v.sku_id,
          flavor_name: v.flavor,
          weight_grams: v.weight_grams,
          weight_display: `${((v.weight_grams || 1000) / 1000).toFixed(1)} kg`,
          lowest_price_inr: bestPrice,
          cost_per_100g_pure_protein: Math.round(costPer100gPure * 10) / 10,
          best_source: liveOffers?.[0]?.platform_name || liveOffers?.[0]?.seller_name || 'Out of Stock',
          price_listings: liveOffers
        };
      });

      const sortedVariants = [...processedVariants]
        .filter((v) => v.lowest_price_inr > 0)
        .sort((a, b) => a.cost_per_100g_pure_protein - b.cost_per_100g_pure_protein);

      return {
        id: prod.id,
        brand_name: prod.brand,
        product_line: prod.base_name,
        category_silo: prod.category_silo,
        purity_percentage: Number(prod.purity_percentage || 0),
        is_amino_spiked: Boolean(prod.is_fairy_dusted),
        best_variant: sortedVariants[0] || null,
        variants: sortedVariants
      };
    });

    return NextResponse.json({
      success: true,
      category: targetSilo,
      count: processData.length,
      data: processData
    });
  } catch (err: any) {
    return NextResponse.json({ error: 'Server initialization failure: ' + (err?.message || err) }, { status: 500 });
  }
}
