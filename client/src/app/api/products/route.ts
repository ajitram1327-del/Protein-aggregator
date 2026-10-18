import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabaseAdmin";
import { apiRatelimit } from "@/lib/ratelimit";
import { MasterUniversalSKU } from "@/types/masterSchema";
import crypto from "crypto";

export const dynamic = "force-dynamic";
export const revalidate = 60; // Cache for 60 seconds

const SIGNING_SECRET = process.env.URL_SIGNING_SECRET || "proteindex-secret-signing-key-32ch";

function generateStoreToken(listingId: string): string {
  const expiresAt = Date.now() + 1000 * 60 * 30; // 30 minutes validity
  const payload = `${listingId}:${expiresAt}`;
  const hmac = crypto.createHmac("sha256", SIGNING_SECRET).update(payload).digest("hex");
  return Buffer.from(`${payload}:${hmac}`).toString("base64url");
}

const VALID_SILOS = new Set([
  "protein",
  "mass_gainers",
  "mass_gainer",
  "gainer",
  "creatine",
  "pre_workout",
  "preworkout",
  "snacks",
  "snack",
  "protein_snacks",
]);

export async function GET(request: NextRequest) {
  try {
    // 1. IP Rate Limiting
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1";
    const { success, limit: rateLimit, remaining, reset } = await apiRatelimit.limit(ip);

    if (!success) {
      return NextResponse.json(
        { error: "Too many requests. Please slow down." },
        {
          status: 429,
          headers: {
            "Retry-After": Math.ceil((reset - Date.now()) / 1000).toString(),
            "X-RateLimit-Limit": rateLimit.toString(),
            "X-RateLimit-Remaining": remaining.toString(),
          },
        }
      );
    }

    const { searchParams } = new URL(request.url);
    const siloParam = (searchParams.get("silo") || searchParams.get("category"))?.trim().toLowerCase();
    const brandParam = searchParams.get("brand")?.trim();
    const flavorParam = searchParams.get("flavor")?.trim();
    const searchParam = searchParams.get("q")?.trim();
    const sortParam = searchParams.get("sort")?.trim().toLowerCase();
    const minPriceParam = searchParams.get("min_price");
    const maxPriceParam = searchParams.get("max_price");
    const pageParam = searchParams.get("page");
    const limitParam = searchParams.get("limit");

    // 2. Strict Pagination Clamping (Hard cap at 1000 items for catalog initialization)
    const page = Math.max(1, parseInt(pageParam || "1", 10));
    let limit = 24;
    if (limitParam !== null && limitParam !== undefined) {
      const parsedLimit = parseInt(limitParam, 10);
      if (isNaN(parsedLimit) || parsedLimit <= 0) {
        return NextResponse.json(
          { error: "Invalid 'limit' parameter. Must be a positive integer between 1 and 1000." },
          { status: 400 }
        );
      }
      limit = Math.min(parsedLimit, 1000);
    }
    const offset = (page - 1) * limit;

    // 3. Parameter Validation & Normalization: Silo
    const SILO_CANONICAL_MAP: Record<string, string> = {
      mass_gainer: "mass_gainers",
      mass_gainers: "mass_gainers",
      gainer: "mass_gainers",
      gainers: "mass_gainers",
      "mass gainers": "mass_gainers",
      protein: "protein",
      whey: "protein",
      plant: "protein",
      whey_protein: "protein",
      whey_: "protein",
      "whey_&_plant_protein": "protein",
      "whey_%26_plant_protein": "protein",
      "whey & plant protein": "protein",
      creatine: "creatine",
      creatine_monohydrate: "creatine",
      "creatine monohydrate": "creatine",
      pre_workout: "pre_workout",
      preworkout: "pre_workout",
      "pre-workout": "pre_workout",
      "pre-workout_": "pre_workout",
      pre_workout_: "pre_workout",
      "pre-workout_&_pump": "pre_workout",
      "pre-workout_%26_pump": "pre_workout",
      "pre-workout & pump": "pre_workout",
      snacks: "snacks",
      snack: "snacks",
      protein_snacks: "snacks",
      protein_snacks_: "snacks",
      "protein_snacks_&_bars": "snacks",
      "protein_snacks_%26_bars": "snacks",
      "protein snacks & bars": "snacks",
    };

    let silo: string | undefined = undefined;
    if (siloParam) {
      if (!VALID_SILOS.has(siloParam) && !SILO_CANONICAL_MAP[siloParam]) {
        return NextResponse.json(
          {
            error: `Invalid 'silo' parameter '${siloParam}'. Permitted categories: protein, mass_gainers, creatine, pre_workout, snacks.`,
          },
          { status: 400 }
        );
      }
      silo = SILO_CANONICAL_MAP[siloParam] || siloParam;
    }

    // 4. Sanitize search and brand against injection characters
    const sanitizedSearch = searchParam ? searchParam.replace(/[,()]/g, ' ').trim() : "";
    const sanitizedBrand = brandParam ? brandParam.replace(/[,()]/g, ' ').trim() : "";
    const sanitizedFlavor = flavorParam ? flavorParam.replace(/[,()]/g, ' ').trim() : "";

    // Parse price bounds
    const minPrice = minPriceParam ? Math.max(0, parseFloat(minPriceParam)) : null;
    const maxPrice = maxPriceParam ? Math.max(0, parseFloat(maxPriceParam)) : null;

    // 5. Query via supabaseAdmin (service role bypasses RLS securely server-side)
    let query = supabaseAdmin
      .from("products")
      .select(`
        id, brand, base_name, category_silo, protein_source, image_url, 
        is_fairy_dusted, lab_verified, trust_score, lab_report_url,
        fssai_license_number, fssai_warning_active,
        variants ( 
          id, sku_id, flavor, weight_grams, lowest_price_inr, best_value_metric, 
          raw_json_data, has_bot_reviews, authenticity_score,
          label_serving_size_g, label_protein_per_serving_g, calculated_purity_pct,
          price_listings ( 
            id, platform_name, source, price_inr, current_price_inr, 
            in_stock, seller_name, is_authorized_seller 
          )
        )
      `, { count: "exact" });

    // Dynamic Database Sorting
    if (sortParam === "trust_desc" || sortParam === "featured") {
      query = query.order("trust_score", { ascending: false }).order("created_at", { ascending: false });
    } else if (sortParam === "newest") {
      query = query.order("created_at", { ascending: false });
    } else {
      query = query.order("trust_score", { ascending: false }).order("created_at", { ascending: false });
    }

    query = query.range(offset, offset + limit - 1);

    if (silo) {
      query = query.eq("category_silo", silo);
    }
    if (sanitizedBrand) {
      query = query.ilike("brand", `%${sanitizedBrand}%`);
    }
    if (sanitizedSearch) {
      query = query.or(`base_name.ilike.%${sanitizedSearch}%,brand.ilike.%${sanitizedSearch}%`);
    }

    const { data, count: totalCount, error } = await query;

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // 6. Transform and sanitize DB rows into Master Universal JSON Schema instances
    let universalSKUs: MasterUniversalSKU[] = [];

    (data || []).forEach((product: any) => {
      // Honeypot defense: Filter out canary variants from public responses
      const visibleVariants = (product.variants || []).filter(
        (v: any) => !v.is_canary && !v.sku_id?.startsWith("PRTX-CANARY") && !v.sku_id?.startsWith("CANARY-")
      );

      // Sort child variants by lowest price ascending
      const sortedVariants = visibleVariants.slice().sort((v1: any, v2: any) => {
        const p1 = Number(v1.lowest_price_inr) || Infinity;
        const p2 = Number(v2.lowest_price_inr) || Infinity;
        return p1 - p2;
      });

      sortedVariants.forEach((v: any) => {
        let rawAnalytics: any = {};
        try {
          if (typeof v.raw_json_data === "string") {
            rawAnalytics = JSON.parse(v.raw_json_data);
          } else if (v.raw_json_data) {
            rawAnalytics = v.raw_json_data;
          }
        } catch {
          rawAnalytics = {};
        }

        const categorySilo = (product.category_silo || "protein").toLowerCase();
        const weightGrams = Math.max(1, Number(v.weight_grams) || 1000);
        
        // Raw values without fallback to 33 / 24
        const rawServingSize = v.label_serving_size_g !== null && v.label_serving_size_g !== undefined ? Number(v.label_serving_size_g) : null;
        const rawProteinPerServing = v.label_protein_per_serving_g !== null && v.label_protein_per_serving_g !== undefined ? Number(v.label_protein_per_serving_g) : null;
        
        // Provenance & Quality Status Evaluation
        let nutritionStatus: "verified" | "observed" | "pending_verification" | "stale" | "unknown" | "not_applicable" = "pending_verification";
        let nutritionReason: string | undefined = undefined;

        if (categorySilo === "creatine") {
          nutritionStatus = "not_applicable";
          nutritionReason = "Creatine purity is measured by creatine monohydrate content, not protein macros.";
        } else if (rawProteinPerServing !== null && rawServingSize !== null && rawServingSize > 0 && rawProteinPerServing > 0) {
          if (rawProteinPerServing > rawServingSize) {
            nutritionStatus = "unknown";
            nutritionReason = "Protein claim exceeds serving scoop size.";
          } else if (product.lab_verified || v.ocr_verified || v.nutrition_audited_at) {
            nutritionStatus = "verified";
          } else {
            nutritionStatus = "observed";
          }
        } else {
          nutritionStatus = "pending_verification";
          nutritionReason = "Serving size or declared protein is pending label audit.";
        }

        const isValidNutrition = nutritionStatus === "verified" || nutritionStatus === "observed";
        const servingSizeGrams = isValidNutrition ? rawServingSize! : 0;
        const proteinPerServing = isValidNutrition ? rawProteinPerServing! : 0;
        const servingsCount = isValidNutrition && servingSizeGrams > 0 ? Math.max(1, Math.round(weightGrams / servingSizeGrams)) : Math.max(1, Math.round(weightGrams / 30));

        // DIAAS calculation adhering to DC-03: must not be inferred from protein % alone
        const declaredDiaas = rawAnalytics?.analytics?.diaas_score ? Number(rawAnalytics.analytics.diaas_score) : null;
        const diaasScore = declaredDiaas && isFinite(declaredDiaas) && declaredDiaas > 0 ? declaredDiaas : null;
        const diaasBasis = rawAnalytics?.analytics?.diaas_basis || (diaasScore ? "Source amino acid assay" : "Unavailable");
        const diaasEvidence = rawAnalytics?.analytics?.diaas_source_evidence || null;
        const aminoStatus = rawAnalytics?.analytics?.amino_acid_completeness_status || (diaasScore ? "COMPLETE" : "UNAUDITED");

        const bioavailableProtein = isValidNutrition && diaasScore ? Number((proteinPerServing * diaasScore).toFixed(1)) : (isValidNutrition ? proteinPerServing : null);
        const purityPct = isValidNutrition && servingSizeGrams > 0 ? Number(((proteinPerServing / servingSizeGrams) * 100).toFixed(1)) : null;

        // Obfuscate raw store URLs behind signed temporary HMAC redirect tokens
        let latestScrapedTime: string | undefined = undefined;
        const offers = (v.price_listings || []).map((pl: any) => {
          if (pl.scraped_at) {
            if (!latestScrapedTime || new Date(pl.scraped_at).getTime() > new Date(latestScrapedTime).getTime()) {
              latestScrapedTime = pl.scraped_at;
            }
          }
          return {
            platform: pl.source || pl.platform_name || "Direct",
            url: pl.id ? `/api/out?token=${generateStoreToken(pl.id)}` : "#",
            priceInr: Math.max(0, Number(pl.current_price_inr || pl.price_inr || 0)),
            inStock: pl.in_stock ?? true,
            sellerName: pl.seller_name || "",
            isAuthorizedSeller: pl.is_authorized_seller ?? true,
            observedAt: pl.scraped_at || new Date().toISOString(),
          };
        });

        const authorizedOffers = offers.filter((o: any) => o.isAuthorizedSeller && o.priceInr > 0);
        const lowestAuthorized = authorizedOffers.length ? Math.min(...authorizedOffers.map((o: any) => o.priceInr)) : undefined;
        const validPrices = offers.map((o: any) => o.priceInr).filter((p: number) => p > 0);
        const lowestPrice = validPrices.length ? Math.min(...validPrices) : (Math.max(0, Number(v.lowest_price_inr)) || 0);
        const hasStock = offers.some((o: any) => o.inStock !== false);

        // Category-specific equalized metric
        let primaryMetricLabel = "₹/g bioavailable protein";
        let primaryMetricValue: number | null = null;
        let secondaryMetricLabel = "Purity %";
        let secondaryMetricValue: number | null = null;
        let isReliable = false;

        if (categorySilo === "creatine") {
          primaryMetricLabel = "₹/3g dose";
          primaryMetricValue = weightGrams > 0 && lowestPrice > 0 ? Number(((lowestPrice / weightGrams) * 3).toFixed(2)) : null;
          secondaryMetricLabel = "Cost/100g";
          secondaryMetricValue = weightGrams > 0 && lowestPrice > 0 ? Number(((lowestPrice / weightGrams) * 100).toFixed(0)) : null;
          isReliable = primaryMetricValue !== null;
        } else if (categorySilo === "mass_gainer" || categorySilo === "mass_gainers") {
          primaryMetricLabel = "₹/1,000 kcal";
          const calories = Number(rawAnalytics?.caloriesPerServing) || 0;
          const totalCals = calories * servingsCount;
          primaryMetricValue = totalCals > 0 && lowestPrice > 0 ? Number(((lowestPrice / totalCals) * 1000).toFixed(1)) : null;
          secondaryMetricLabel = "Serving Count";
          secondaryMetricValue = servingsCount;
          isReliable = primaryMetricValue !== null;
        } else if (categorySilo === "pre_workout" || categorySilo === "preworkout") {
          primaryMetricLabel = "₹/scoop";
          primaryMetricValue = servingsCount > 0 && lowestPrice > 0 ? Number((lowestPrice / servingsCount).toFixed(1)) : null;
          secondaryMetricLabel = "Total Scoops";
          secondaryMetricValue = servingsCount;
          isReliable = primaryMetricValue !== null;
        } else if (categorySilo === "snacks" || categorySilo === "snack" || categorySilo === "protein_snacks") {
          primaryMetricLabel = "₹/100g";
          const effectiveGrams = weightGrams > 0 ? weightGrams : (servingSizeGrams > 0 ? servingSizeGrams : 100);
          primaryMetricValue = effectiveGrams > 0 && lowestPrice > 0 ? Number(((lowestPrice / effectiveGrams) * 100).toFixed(1)) : null;
          secondaryMetricLabel = "Protein/Serving (g)";
          secondaryMetricValue = proteinPerServing > 0 ? proteinPerServing : null;
          isReliable = primaryMetricValue !== null;
        } else {
          // Standard Protein Silo: ₹/g protein using total package protein
          if (isValidNutrition && proteinPerServing > 0 && servingsCount > 0 && lowestPrice > 0) {
            const effectiveProteinPool = servingsCount * (bioavailableProtein || proteinPerServing);
            primaryMetricValue = effectiveProteinPool > 0 ? Number((lowestPrice / effectiveProteinPool).toFixed(2)) : null;
            secondaryMetricLabel = "Purity %";
            secondaryMetricValue = purityPct;
            isReliable = true;
          } else {
            primaryMetricValue = null;
            secondaryMetricValue = null;
            isReliable = false;
          }
        }

        universalSKUs.push({
          skuId: v.sku_id || `${(product.brand || "brand").toLowerCase()}-${(v.flavor || "flavor").toLowerCase()}-${weightGrams}g`,
          brand: product.brand || "Unknown",
          productName: product.base_name || "Protein",
          categorySilo: product.category_silo || "protein",
          subCategory: product.protein_source || "Whey Blend",
          flavor: v.flavor || "Unflavored",
          imageUrl: product.image_url || "",
          packaging: {
            weightGrams,
            servingsCount,
            servingSizeGrams,
          },
          nutritionalProfile: {
            activeIngredientPerServingGrams: isValidNutrition ? proteinPerServing : null,
            pdcaasScore: diaasScore,
            bioavailableProteinPerServing: bioavailableProtein,
            proteinPurityPct: purityPct,
            caloriesPerServing: isValidNutrition ? Number(rawAnalytics?.caloriesPerServing) || null : null,
            carbsPerServingGrams: isValidNutrition ? Number(rawAnalytics?.carbsPerServing) || null : null,
            nutritionStatus,
            nutritionStatusReason: nutritionReason,
            diaasScore,
            diaasBasis,
            diaasSourceEvidence: diaasEvidence,
            aminoAcidCompletenessStatus: aminoStatus,
          },
          usefulDoseAnalysis: {
            leucinePerServingGrams: isValidNutrition && proteinPerServing >= 20 ? Number((proteinPerServing * 0.11).toFixed(1)) : null,
            meetsMpsThreshold: isValidNutrition ? proteinPerServing >= 20 : null,
            aminoSpikeRisk: Boolean(rawAnalytics?.aminoSpikeRisk),
            fillersDetected: product.is_fairy_dusted ? ["Maltodextrin"] : [],
          },
          equalizerMetrics: {
            primaryMetricLabel,
            primaryMetricValue,
            secondaryMetricLabel,
            secondaryMetricValue,
            isReliable,
          },
          pricing: {
            lowestPriceInr: lowestPrice,
            lowestAuthorizedPriceInr: lowestAuthorized,
            sellerCount: offers.length,
            lastObservedAt: latestScrapedTime || new Date().toISOString(),
            inStock: hasStock,
            vendorOffers: offers,
          },
          verification: {
            tier: product.lab_verified ? "gold" : "bronze",
            fssai: {
              licenseNumber: product.fssai_license_number || undefined,
              status: product.fssai_warning_active ? "FLAGGED" : "ACTIVE",
              verifiedManufacturer: product.brand,
            },
            records: product.lab_verified
              ? [
                  {
                    authority: "Trustified NABL",
                    labName: "Eurofins",
                    status: "PASS",
                    proofUrl: product.lab_report_url || undefined,
                  },
                ]
              : [],
          },
        });
      });
    });

    // In-Memory Flavor & Price Filters for Child Variants
    if (sanitizedFlavor) {
      universalSKUs = universalSKUs.filter((sku) =>
        sku.flavor.toLowerCase().includes(sanitizedFlavor.toLowerCase())
      );
    }
    if (minPrice !== null) {
      universalSKUs = universalSKUs.filter(
        (sku) => sku.pricing.lowestPriceInr >= minPrice
      );
    }
    if (maxPrice !== null) {
      universalSKUs = universalSKUs.filter(
        (sku) => sku.pricing.lowestPriceInr <= maxPrice
      );
    }

    // Secondary In-Memory Sorting
    if (sortParam === "price_asc" || sortParam === "price-asc") {
      universalSKUs.sort((a, b) => a.pricing.lowestPriceInr - b.pricing.lowestPriceInr);
    } else if (sortParam === "price_desc" || sortParam === "price-desc") {
      universalSKUs.sort((a, b) => b.pricing.lowestPriceInr - a.pricing.lowestPriceInr);
    } else if (sortParam === "value_asc" || sortParam === "value-asc") {
      universalSKUs.sort((a, b) => {
        const valA = a.equalizerMetrics.primaryMetricValue ?? Infinity;
        const valB = b.equalizerMetrics.primaryMetricValue ?? Infinity;
        return valA - valB;
      });
    } else if (sortParam === "purity_desc" || sortParam === "purity-desc") {
      universalSKUs.sort((a, b) => {
        const purA = a.nutritionalProfile.proteinPurityPct ?? 0;
        const purB = b.nutritionalProfile.proteinPurityPct ?? 0;
        return purB - purA;
      });
    }

    return NextResponse.json(
      {
        page,
        page_size: limit,
        total_count: totalCount ?? universalSKUs.length,
        count: universalSKUs.length,
        data: universalSKUs,
      },
      {
        headers: {
          "Cache-Control": "public, s-maxage=120, stale-while-revalidate=300",
          "X-Content-Type-Options": "nosniff",
          "X-Total-Count": (totalCount ?? universalSKUs.length).toString(),
        },
      }
    );
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Internal Server Error" }, { status: 500 });
  }
}
