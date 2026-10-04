import re

with open("client/src/App.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update DbPriceListing
content = content.replace(
    "  source_url: string;\n}",
    "  source_url: string;\n  seller_name?: string;\n  is_authorized_seller?: boolean;\n}"
)

# 2. Update DbVariant
content = content.replace(
    "  price_listings: DbPriceListing[];\n}",
    "  price_listings: DbPriceListing[];\n  has_bot_reviews?: boolean;\n  authenticity_score?: number;\n}"
)

# 3. Update GroupedProduct
content = content.replace(
    "  bestValueMetric: number;\n}",
    "  bestValueMetric: number;\n  isFairyDusted?: boolean;\n  labVerified?: boolean;\n  trustScore?: number;\n  labReportUrl?: string;\n}"
)

# 4. Update Select Query
old_query = """          id, brand, base_name, category_silo, protein_source, image_url,
          variants ( 
            sku_id, flavor, weight_grams, lowest_price_inr, best_value_metric, raw_json_data,
            price_listings ( source, price_inr, source_url )"""
new_query = """          id, brand, base_name, category_silo, protein_source, image_url, is_fairy_dusted, lab_verified, trust_score, lab_report_url,
          variants ( 
            sku_id, flavor, weight_grams, lowest_price_inr, best_value_metric, raw_json_data, has_bot_reviews, authenticity_score,
            price_listings ( source, price_inr, source_url, seller_name, is_authorized_seller )"""
content = content.replace(old_query, new_query)

# 5. Update Mapping
old_mapping = """            imageUrl: p.image_url,
            variants: p.variants,
            lowestPrice,
            bestValueMetric: bestValue
          };"""
new_mapping = """            imageUrl: p.image_url,
            variants: p.variants,
            lowestPrice,
            bestValueMetric: bestValue,
            isFairyDusted: p.is_fairy_dusted,
            labVerified: p.lab_verified,
            trustScore: p.trust_score,
            labReportUrl: p.lab_report_url
          };"""
content = content.replace(old_mapping, new_mapping)

# 6. Add Lab Verified Shield and Fairy Dusted Banner
header = """              {/* Header and Quick Stats */}"""
new_header = """              {/* Warning Banner */}
              {selectedGroup.isFairyDusted && (
                <div className="mb-4 bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg text-sm font-mono flex items-center gap-2">
                  <span className="font-bold text-red-600">⚠️ PROPRIETARY BLEND ALERT:</span>
                  This product has been algorithmically flagged for "Fairy-Dusting" (cheap fillers like maltodextrin/taurine are listed before premium ingredients).
                </div>
              )}

              {/* Header and Quick Stats */}"""
content = content.replace(header, new_header)

title = """<h1 className="text-2xl font-black uppercase tracking-tight text-[#111827]">{selectedGroup.baseProductName}</h1>"""
new_title = """<div className="flex items-center gap-3">
                    <h1 className="text-2xl font-black uppercase tracking-tight text-[#111827]">{selectedGroup.baseProductName}</h1>
                    {selectedGroup.labVerified && (
                      <a href={selectedGroup.labReportUrl} target="_blank" rel="noopener noreferrer" className="bg-yellow-50 border border-yellow-200 text-yellow-800 text-[10px] font-bold px-2 py-1 rounded-md flex items-center gap-1 uppercase tracking-wider hover:bg-yellow-100 cursor-pointer">
                        🛡️ 3rd-Party Lab Verified
                      </a>
                    )}
                  </div>"""
content = content.replace(title, new_title)

# 7. Add Bot Reviews Warning on Variant Selection
variant_sizes = """                       <div className="text-xs font-mono font-bold uppercase text-[#374151] mb-2">Available Sizes</div>"""
new_variant_sizes = """                       {selectedVariant?.has_bot_reviews && (
                         <div className="mb-4 bg-orange-50 border border-orange-200 text-orange-800 px-3 py-2 rounded-md text-[11px] font-mono flex items-center gap-2">
                           <span className="font-bold">BOT RISK:</span>
                           Authenticity Score {selectedVariant.authenticity_score}/100. High lexical overlap detected in recent 5-star reviews.
                         </div>
                       )}
                       <div className="text-xs font-mono font-bold uppercase text-[#374151] mb-2">Available Sizes</div>"""
content = content.replace(variant_sizes, new_variant_sizes)

# 8. Modify Table to handle Seller and Auth Seller
table_headers = """                    <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB] text-[#6B7280] uppercase text-[11px]">
                      <th className="p-3 font-semibold">Retailer</th>
                      <th className="p-3 font-semibold">Stock</th>
                      <th className="p-3 font-semibold">Cost / Bio-G</th>
                      <th className="p-3 font-semibold text-right">Price</th>
                      <th className="p-3 font-semibold text-right">Action</th>
                    </tr>"""
new_table_headers = """                    <tr className="border-b border-[#E5E7EB] bg-[#F9FAFB] text-[#6B7280] uppercase text-[11px]">
                      <th className="p-3 font-semibold">Retailer / Seller</th>
                      <th className="p-3 font-semibold">Stock</th>
                      <th className="p-3 font-semibold">Cost / Bio-G</th>
                      <th className="p-3 font-semibold text-right">Price</th>
                      <th className="p-3 font-semibold text-right">Action</th>
                    </tr>"""
content = content.replace(table_headers, new_table_headers)

table_row = """                          <td className="p-3">
                            <div className="font-bold text-[#111827]">{offer.source}</div>
                          </td>"""
new_table_row = """                          <td className="p-3">
                            <div className="font-bold text-[#111827] flex items-center gap-2">
                              {offer.source}
                              {offer.is_authorized_seller === False && (
                                <span className="bg-red-100 text-red-700 text-[9px] px-1.5 py-0.5 rounded">UNAUTHORIZED</span>
                              )}
                            </div>
                            {offer.seller_name && <div className="text-[10px] text-gray-500 mt-0.5">Sold by: {offer.seller_name}</div>}
                          </td>"""
content = content.replace(table_row, new_table_row)

is_best = "const isBest = idx === 0;"
# We need to find the lowest authorized price
is_best_logic = """const isBest = offer.price_inr === Math.min(...(selectedVariant?.price_listings?.filter(l => l.is_authorized_seller !== false).map(l => l.price_inr) || [])) && offer.is_authorized_seller !== false;"""
content = content.replace(is_best, is_best_logic)

with open("client/src/App.tsx", "w", encoding="utf-8") as f:
    f.write(content)
