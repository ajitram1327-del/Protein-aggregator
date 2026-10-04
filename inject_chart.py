import re

with open('client/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "import { CompareTray } from './components/CompareTray'", 
    "import { CompareTray } from './components/CompareTray'\nimport { PriceHistoryChart } from './components/PriceHistoryChart'"
)

target_block = """        </div>

        {/* Aggregated Listings Table */}"""
        
new_block = """        </div>

        {/* Price History Tracking Chart */}
        <PriceHistoryChart 
          variantId={currentVariant?.id || currentVariant?.sku_id} 
          variantName={`${product.brand} - ${currentVariant?.flavor} (${currentVariant?.weight_grams}g)`}
          proteinPerServing={24}
          servings={currentVariant?.raw_json_data?.analytics?.total_absorbed_protein_pool_g ? Math.round(currentVariant.raw_json_data.analytics.total_absorbed_protein_pool_g / 24) : 30}
        />

        {/* Aggregated Listings Table */}"""
        
content = content.replace(target_block, new_block)

with open('client/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
