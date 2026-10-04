import { NextRequest, NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { ProductListingView } from '@/types/masterSchema';
import { generateAffiliateUrl } from '@/utils/affiliate';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const idsParam = searchParams.get('ids');
    const snapshotId = searchParams.get('snapshotId');

    let variantIds: string[] = [];

    if (snapshotId) {
      if (!UUID_REGEX.test(snapshotId.trim())) {
        return NextResponse.json(
          { error: "Invalid 'snapshotId' format. Must be a valid UUID." },
          { status: 400 }
        );
      }

      // Fetch snapshot from comparison_snapshots
      const { data: snapshot, error: snapError } = await supabase
        .from('comparison_snapshots')
        .select('variant_ids')
        .eq('id', snapshotId.trim())
        .single();

      if (snapError || !snapshot) {
        return NextResponse.json({ error: 'Comparison snapshot not found or expired' }, { status: 404 });
      }
      variantIds = snapshot.variant_ids;
    } else if (idsParam) {
      const rawIds = idsParam
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      const invalidIds = rawIds.filter((id) => !UUID_REGEX.test(id));
      if (invalidIds.length > 0) {
        return NextResponse.json(
          { error: `Invalid UUID format for variant ID(s): ${invalidIds.join(', ')}` },
          { status: 400 }
        );
      }

      variantIds = Array.from(new Set(rawIds));
    } else {
      return NextResponse.json(
        { error: "Missing required parameter. Provide 'ids' (comma-separated UUIDs) or 'snapshotId'." },
        { status: 400 }
      );
    }

    if (variantIds.length < 2 || variantIds.length > 4) {
      return NextResponse.json(
        { error: 'Comparison requires between 2 and 4 distinct variant IDs' },
        { status: 400 }
      );
    }

    // Query variants joined with products and price_listings
    const { data: variants, error } = await supabase
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

    if (error) {
      return NextResponse.json({ error: error.message || 'Failed to fetch variants' }, { status: 500 });
    }

    if (!variants || variants.length < 2) {
      const foundCount = variants ? variants.length : 0;
      return NextResponse.json(
        {
          error: `Only ${foundCount} of ${variantIds.length} requested variant(s) exist in the database. Comparison requires at least 2 active variants.`,
        },
        { status: 404 }
      );
    }

    // Map each variant to ProductListingView
    const comparedRows: ProductListingView[] = variants.map((v: any) => {
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

      // Preferred authorized offer
      const bestOffer = authorizedListings.length
        ? authorizedListings.reduce((min: any, cur: any) =>
            Number(cur.current_price_inr || cur.price_inr) < Number(min.current_price_inr || min.price_inr) ? cur : min
          )
        : inStockListings.length
        ? inStockListings.reduce((min: any, cur: any) =>
            Number(cur.current_price_inr || cur.price_inr) < Number(min.current_price_inr || min.price_inr) ? cur : min
          )
        : null;

      const lowestPrice = bestOffer ? Math.max(0, Number(bestOffer.current_price_inr || bestOffer.price_inr)) : (Math.max(0, Number(v.lowest_price_inr)) || 0);
      const platformName = bestOffer?.platform_name || bestOffer?.source || 'Direct';
      const rawUrl = bestOffer?.source_url || bestOffer?.listing_url || '';
      const affiliateUrl = generateAffiliateUrl(rawUrl, platformName);

      const diaas = Math.max(0, Number(rawAnalytics?.analytics?.diaas_score) || 1.0);
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

    // Optionally create snapshot only when variants exist
    let createdSnapshotId: string | undefined = undefined;
    if (!snapshotId && comparedRows.length >= 2) {
      const activeVariantIds = comparedRows.map((r) => r.variantId);
      const { data: newSnap } = await supabase
        .from('comparison_snapshots')
        .insert({ variant_ids: activeVariantIds })
        .select('id')
        .single();

      if (newSnap) {
        createdSnapshotId = newSnap.id;
      }
    }

    return NextResponse.json({
      snapshotId: snapshotId || createdSnapshotId,
      comparedCount: comparedRows.length,
      data: comparedRows,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || 'Comparison failed' }, { status: 500 });
  }
}
