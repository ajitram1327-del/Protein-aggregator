import { GroupedProduct, DbVariant } from "@/types/products";
import { MasterUniversalSKU } from "@/types/masterSchema";
import { GET } from "@/app/api/products/route";
import { NextRequest } from "next/server";

export interface ProductsFetchResult {
  products: GroupedProduct[];
  errorMsg: string;
}

export async function getGroupedProducts(params?: {
  silo?: string;
  brand?: string;
  q?: string;
  limit?: number;
}): Promise<ProductsFetchResult> {
  const baseUrl =
    process.env.NEXT_PUBLIC_APP_URL ||
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

  let data: MasterUniversalSKU[] = [];
  let errorMsg = "";

  try {
    const url = new URL(`${baseUrl}/api/products`);
    if (params?.silo) url.searchParams.set("silo", params.silo);
    if (params?.brand) url.searchParams.set("brand", params.brand);
    if (params?.q) url.searchParams.set("q", params.q);
    if (params?.limit) url.searchParams.set("limit", params.limit.toString());
    else url.searchParams.set("limit", "100");

    const req = new NextRequest(url);
    const res = await GET(req);

    if (!res.ok) {
      let detail = "";
      try {
        const errJson = await res.json();
        detail = errJson.error || errJson.message || JSON.stringify(errJson);
      } catch {
        detail = res.statusText || "";
      }
      errorMsg = `HTTP error! status: ${res.status}${detail ? ` - ${detail}` : ""}`;
    } else {
      const json = await res.json();
      data = json.data || [];
    }
  } catch (err: any) {
    errorMsg = err.message || "Failed to fetch data";
  }

  if (errorMsg) {
    return { products: [], errorMsg };
  }

  // Group by Product
  const grouped: Record<string, GroupedProduct> = {};

  data.forEach((sku) => {
    const key = `${sku.brand}-${sku.productName}`;
    if (!grouped[key]) {
      grouped[key] = {
        id: sku.skuId,
        brand: sku.brand,
        baseProductName: sku.productName,
        categorySilo: sku.categorySilo,
        proteinSource: sku.subCategory,
        imageUrl: sku.imageUrl || "",
        variants: [],
        lowestPrice: Infinity,
        bestValueMetric: Infinity,
        isFairyDusted: sku.usefulDoseAnalysis.fillersDetected.length > 0,
        aminoSpikeRisk: Boolean(sku.usefulDoseAnalysis.aminoSpikeRisk),
        aminoSpikeBadge: sku.usefulDoseAnalysis.aminoSpikeRisk ? "⚠️ High Amino Spiking Risk" : undefined,
        labVerified: sku.verification.tier === "gold",
        trustScore: sku.usefulDoseAnalysis.aminoSpikeRisk ? 60 : 100,
        labReportUrl: sku.verification.records[0]?.proofUrl || "",
      };
    }

    const group = grouped[key];

    const variant: DbVariant = {
      id: sku.skuId,
      sku_id: sku.skuId,
      flavor: sku.flavor,
      weight_grams: sku.packaging.weightGrams,
      lowest_price_inr: sku.pricing.lowestPriceInr,
      best_value_metric: sku.equalizerMetrics.primaryMetricValue,
      raw_json_data: {
        nutritionStatus: sku.nutritionalProfile.nutritionStatus,
        diaasScore: sku.nutritionalProfile.diaasScore,
        diaasBasis: sku.nutritionalProfile.diaasBasis,
        usefulDoseAnalysis: sku.usefulDoseAnalysis,
      },
      label_serving_size_g: sku.packaging.servingSizeGrams || null,
      label_protein_per_serving_g: sku.nutritionalProfile.activeIngredientPerServingGrams || null,
      calculated_purity_pct: sku.nutritionalProfile.proteinPurityPct || null,
      nutrition_status: sku.nutritionalProfile.nutritionStatus,
      last_observed_at: sku.pricing.lastObservedAt,
      seller_count: sku.pricing.sellerCount,
      price_listings: sku.pricing.vendorOffers.map((o) => ({
        source: o.platform,
        price_inr: o.priceInr,
        source_url: o.url,
        seller_name: o.sellerName,
        is_authorized_seller: o.isAuthorizedSeller,
        in_stock: o.inStock,
        scraped_at: o.observedAt,
      })),
      authenticity_score: undefined,
      has_bot_reviews: undefined,
    };

    group.variants.push(variant);

    if (variant.lowest_price_inr < group.lowestPrice) {
      group.lowestPrice = variant.lowest_price_inr;
    }
    if (
      variant.best_value_metric !== null &&
      variant.best_value_metric > 0 &&
      variant.best_value_metric < (group.bestValueMetric ?? Infinity)
    ) {
      group.bestValueMetric = variant.best_value_metric;
    }
  });

  // Sort child variants by lowest price ascending
  Object.values(grouped).forEach((group) => {
    group.variants.sort((v1, v2) => {
      const p1 = v1.lowest_price_inr || Infinity;
      const p2 = v2.lowest_price_inr || Infinity;
      if (p1 !== p2) return p1 - p2;
      return (v1.best_value_metric || Infinity) - (v2.best_value_metric || Infinity);
    });
  });

  return {
    products: Object.values(grouped),
    errorMsg: "",
  };
}

export async function getProductBySkuOrId(skuOrId: string): Promise<GroupedProduct | null> {
  const { products } = await getGroupedProducts({ limit: 100 });
  const normalized = decodeURIComponent(skuOrId).toLowerCase().trim();

  return (
    products.find((p) => {
      if (p.id.toLowerCase() === normalized) return true;
      if (p.baseProductName.toLowerCase() === normalized) return true;
      if (
        p.variants.some(
          (v) =>
            v.id.toLowerCase() === normalized ||
            v.sku_id.toLowerCase() === normalized
        )
      ) {
        return true;
      }
      return false;
    }) || null
  );
}
