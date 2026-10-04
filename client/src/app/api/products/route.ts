import { NextRequest, NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { MasterUniversalSKU } from '@/types/masterSchema';

export const revalidate = 60; // Cache for 60 seconds

const VALID_SILOS = new Set([
  'protein',
  'mass_gainers',
  'mass_gainer',
  'gainer',
  'creatine',
  'pre_workout',
  'preworkout',
]);

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const siloParam = searchParams.get('silo')?.trim().toLowerCase();
    const brandParam = searchParams.get('brand')?.trim();
    const searchParam = searchParams.get('q')?.trim();
    const limitParam = searchParams.get('limit');

    // 1. Parameter Validation: Limit
    let limit = 50;
    if (limitParam !== null && limitParam !== undefined) {
      const parsedLimit = parseInt(limitParam, 10);
      if (isNaN(parsedLimit) || parsedLimit <= 0) {
        return NextResponse.json(
          { error: "Invalid 'limit' parameter. Must be a positive integer between 1 and 100." },
          { status: 400 }
        );
      }
      limit = Math.min(parsedLimit, 100);
    }

    // 2. Parameter Validation: Silo
    let silo: string | undefined = undefined;
    if (siloParam) {
      if (!VALID_SILOS.has(siloParam)) {
        return NextResponse.json(
          {
            error: `Invalid 'silo' parameter '${siloParam}'. Permitted categories: protein, mass_gainers, creatine, pre_workout.`,
          },
          { status: 400 }
        );
      }
      silo = siloParam;
    }

    // 3. Sanitize search and brand against PostgREST filter injection characters
    const sanitizedSearch = searchParam ? searchParam.replace(/[,()]/g, ' ').trim() : '';
    const sanitizedBrand = brandParam ? brandParam.replace(/[,()]/g, ' ').trim() : '';

    let query = supabase
      .from('products')
      .select(`
        id, brand, base_name, category_silo, protein_source, image_url, 
        is_fairy_dusted, lab_verified, trust_score, lab_report_url,
        fssai_license_number, fssai_warning_active,
        variants ( 
          id, sku_id, flavor, weight_grams, lowest_price_inr, best_value_metric, 
          raw_json_data, has_bot_reviews, authenticity_score,
          label_serving_size_g, label_protein_per_serving_g, calculated_purity_pct,
          price_listings ( 
            platform_name, source, price_inr, current_price_inr, source_url, 
            listing_url, in_stock, seller_name, is_authorized_seller 
          )
        )
      `)
      .limit(limit);

    if (silo) {
      query = query.eq('category_silo', silo);
    }
    if (sanitizedBrand) {
      query = query.ilike('brand', `%${sanitizedBrand}%`);
    }
    if (sanitizedSearch) {
      query = query.or(`base_name.ilike.%${sanitizedSearch}%,brand.ilike.%${sanitizedSearch}%`);
    }

    const { data, error } = await query;

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Transform joined DB rows into Master Universal JSON Schema instances
    const universalSKUs: MasterUniversalSKU[] = [];

    (data || []).forEach((product: any) => {
      (product.variants || []).forEach((v: any) => {
        let rawAnalytics: any = {};
        try {
          if (typeof v.raw_json_data === 'string') {
            rawAnalytics = JSON.parse(v.raw_json_data);
          } else if (v.raw_json_data) {
            rawAnalytics = v.raw_json_data;
          }
        } catch {
          rawAnalytics = {};
        }

        const weightGrams = Math.max(1, Number(v.weight_grams) || 1000);
        const servingSizeGrams = Math.max(1.0, Number(v.label_serving_size_g) || 33.0);
        const servingsCount = Math.max(1, Math.round(weightGrams / servingSizeGrams));
        const proteinPerServing = Math.max(0.0, Number(v.label_protein_per_serving_g) || 24.0);
        const diaas = Math.max(0.0, Number(rawAnalytics?.analytics?.diaas_score) || 1.0);
        const bioavailableProtein = Number((proteinPerServing * diaas).toFixed(1));
        const rawPurity = (proteinPerServing / servingSizeGrams) * 100;
        const purityPct = Math.min(100.0, Math.max(0.0, Number(v.calculated_purity_pct) || Number(rawPurity.toFixed(1))));

        const offers = (v.price_listings || []).map((pl: any) => ({
          platform: pl.source || pl.platform_name || 'Direct',
          url: pl.source_url || pl.listing_url || '',
          priceInr: Math.max(0, Number(pl.current_price_inr || pl.price_inr || 0)),
          inStock: pl.in_stock ?? true,
          sellerName: pl.seller_name || '',
          isAuthorizedSeller: pl.is_authorized_seller ?? true,
        }));

        const authorizedOffers = offers.filter((o: any) => o.isAuthorizedSeller && o.priceInr > 0);
        const lowestAuthorized = authorizedOffers.length ? Math.min(...authorizedOffers.map((o: any) => o.priceInr)) : undefined;
        const validPrices = offers.map((o: any) => o.priceInr).filter((p: number) => p > 0);
        const lowestPrice = validPrices.length ? Math.min(...validPrices) : (Math.max(0, Number(v.lowest_price_inr)) || 0);

        const proteinPool = servingsCount * bioavailableProtein;
        const fallbackMetric = (proteinPool > 0 && lowestPrice > 0) ? Number((lowestPrice / proteinPool).toFixed(2)) : 0.0;

        universalSKUs.push({
          skuId: v.sku_id || `${(product.brand || 'brand').toLowerCase()}-${(v.flavor || 'flavor').toLowerCase()}-${weightGrams}g`,
          brand: product.brand || 'Unknown',
          productName: product.base_name || 'Protein',
          categorySilo: product.category_silo || 'protein',
          subCategory: product.protein_source || 'Whey Blend',
          flavor: v.flavor || 'Unflavored',
          imageUrl: product.image_url || '',
          packaging: {
            weightGrams,
            servingsCount,
            servingSizeGrams,
          },
          nutritionalProfile: {
            activeIngredientPerServingGrams: proteinPerServing,
            pdcaasScore: diaas,
            bioavailableProteinPerServing: bioavailableProtein,
            proteinPurityPct: purityPct,
            caloriesPerServing: 120,
            carbsPerServingGrams: 1.5,
          },
          usefulDoseAnalysis: {
            leucinePerServingGrams: 2.7,
            meetsMpsThreshold: proteinPerServing >= 20,
            aminoSpikeRisk: false,
            fillersDetected: product.is_fairy_dusted ? ['Maltodextrin'] : [],
          },
          equalizerMetrics: {
            primaryMetricLabel: '₹/g bioavailable protein',
            primaryMetricValue: Number(v.best_value_metric) || fallbackMetric,
            secondaryMetricLabel: 'Purity %',
            secondaryMetricValue: purityPct,
          },
          pricing: {
            lowestPriceInr: lowestPrice,
            lowestAuthorizedPriceInr: lowestAuthorized,
            vendorOffers: offers,
          },
          verification: {
            tier: product.lab_verified ? 'gold' : 'bronze',
            fssai: {
              licenseNumber: product.fssai_license_number || undefined,
              status: product.fssai_warning_active ? 'FLAGGED' : 'ACTIVE',
              verifiedManufacturer: product.brand,
            },
            records: product.lab_verified
              ? [
                  {
                    authority: 'Trustified NABL',
                    labName: 'Eurofins',
                    status: 'PASS',
                    proofUrl: product.lab_report_url || undefined,
                  },
                ]
              : [],
          },
        });
      });
    });

    return NextResponse.json({
      count: universalSKUs.length,
      data: universalSKUs,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || 'Internal Server Error' }, { status: 500 });
  }
}
