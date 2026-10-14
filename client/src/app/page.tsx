import { ProductBrowser, GroupedProduct, DbVariant } from '@/components/ProductBrowser'
import { MasterUniversalSKU } from '@/types/masterSchema'
import { GET } from '@/app/api/products/route'
import { NextRequest } from 'next/server'

export const revalidate = 60 // Revalidate cache every 60 seconds

export default async function Home() {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000')
  let data: MasterUniversalSKU[] = []
  let errorMsg = ''

  try {
    const req = new NextRequest(new URL(`${baseUrl}/api/products`))
    const res = await GET(req)
    if (!res.ok) {
      errorMsg = `HTTP error! status: ${res.status}`
    } else {
      const json = await res.json()
      data = json.data || []
    }
  } catch (err: any) {
    errorMsg = err.message || 'Failed to fetch data'
  }

  if (errorMsg) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50">
        <h1 className="text-2xl font-bold text-slate-800 mb-4">Oops! Something went wrong.</h1>
        <p className="text-slate-600">We couldn&apos;t load the products. Please try again later.</p>
        <p className="text-sm text-red-500 mt-4">{errorMsg}</p>
      </div>
    )
  }

  // Group by Product
  const grouped: Record<string, GroupedProduct> = {}
  data.forEach((sku) => {
    const key = `${sku.brand}-${sku.productName}`
    if (!grouped[key]) {
      grouped[key] = {
        id: sku.skuId, // fallback since API doesn't expose product id
        brand: sku.brand,
        baseProductName: sku.productName,
        categorySilo: sku.categorySilo,
        proteinSource: sku.subCategory,
        imageUrl: sku.imageUrl || '',
        variants: [],
        lowestPrice: Infinity,
        bestValueMetric: Infinity,
        isFairyDusted: sku.usefulDoseAnalysis.fillersDetected.length > 0,
        labVerified: sku.verification.tier === 'gold',
        trustScore: 100, // API doesn't expose it, fallback
        labReportUrl: sku.verification.records[0]?.proofUrl || '',
      }
    }

    const group = grouped[key]

    const variant: DbVariant = {
      id: sku.skuId,
      sku_id: sku.skuId,
      flavor: sku.flavor,
      weight_grams: sku.packaging.weightGrams,
      lowest_price_inr: sku.pricing.lowestPriceInr,
      best_value_metric: sku.equalizerMetrics.primaryMetricValue,
      raw_json_data: null,
      label_serving_size_g: sku.packaging.servingSizeGrams || 33,
      label_protein_per_serving_g: sku.nutritionalProfile.activeIngredientPerServingGrams || 24,
      calculated_purity_pct: sku.nutritionalProfile.proteinPurityPct || 75,
      price_listings: sku.pricing.vendorOffers.map((o) => ({
        source: o.platform,
        price_inr: o.priceInr,
        source_url: o.url,
        seller_name: o.sellerName,
        is_authorized_seller: o.isAuthorizedSeller,
      })),
      authenticity_score: undefined,
      has_bot_reviews: undefined,
    }

    group.variants.push(variant)

    if (variant.lowest_price_inr < group.lowestPrice) {
      group.lowestPrice = variant.lowest_price_inr
    }
    if (variant.best_value_metric > 0 && variant.best_value_metric < group.bestValueMetric) {
      group.bestValueMetric = variant.best_value_metric
    }
  })

  const formatted = Object.values(grouped)

  return <ProductBrowser initialProducts={formatted} />
}
