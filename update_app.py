import re

with open('client/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
imports = """import { CompareView } from './components/CompareView'
import { CompareTray } from './components/CompareTray'
"""
content = content.replace("import './App.css'", "import './App.css'\n" + imports)

# 2. Add 'id' to Variant interface and fetch query
content = content.replace("  sku_id: string;", "  id: string;\n  sku_id: string;")
content = content.replace(
    "variants ( \n            sku_id",
    "variants ( \n            id, sku_id"
)

# 3. Main App Component State
main_comp = """export default function App() {
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<GroupedProduct[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSilo, setActiveSilo] = useState<string | null>(null);
  
  // COMPARE TRAY STATE
  const [compareQueue, setCompareQueue] = useState<any[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  const isCompareView = new URLSearchParams(window.location.search).has('snapshot');
"""

old_main_comp = """export default function App() {
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<GroupedProduct[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSilo, setActiveSilo] = useState<string | null>(null);"""
content = content.replace(old_main_comp, main_comp)

# 4. Handle Compare Functions inside App
compare_funcs = """
  const handleToggleCompare = (variantId: string, brand: string, flavor: string) => {
    setCompareQueue(prev => {
      const exists = prev.find(item => item.variantId === variantId);
      if (exists) return prev.filter(item => item.variantId !== variantId);
      if (prev.length >= 4) return prev;
      return [...prev, { variantId, brand, flavor }];
    });
  };

  const generateSnapshot = async () => {
    setIsGenerating(true);
    try {
      const variantIds = compareQueue.map(q => q.variantId);
      const { data, error } = await supabase
        .from('comparison_snapshots')
        .insert([{ variant_ids: variantIds }])
        .select()
        .single();
      
      if (data) {
        window.location.href = `/?snapshot=${data.id}`;
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsGenerating(false);
    }
  };

  if (isCompareView) {
    return <CompareView />;
  }
"""

use_effect = """  useEffect(() => {"""
content = content.replace(use_effect, compare_funcs + "\n" + use_effect)

# 5. Modify ProteinTerminal to accept compare props
old_terminal_sig = """function ProteinTerminal({ product, onClose }: { product: GroupedProduct, onClose: () => void }) {"""
new_terminal_sig = """function ProteinTerminal({ product, onClose, compareQueue, onToggleCompare }: { product: GroupedProduct, onClose: () => void, compareQueue: any[], onToggleCompare: (vId: string, b: string, f: string) => void }) {"""
content = content.replace(old_terminal_sig, new_terminal_sig)

# 6. Add Compare button in Variant Matrix (inside ProteinTerminal)
old_variant_button = """                  <div className={`text-[11px] mt-1 ${active ? "text-gray-300" : "text-[#6B7280]"}`}>
                    {v.weight_grams}g • {v.raw_json_data?.analytics?.total_absorbed_protein_pool_g ? Math.round(v.raw_json_data.analytics.total_absorbed_protein_pool_g / 24) : 30} Servings
                  </div>
                </button>"""
new_variant_button = """                  <div className={`text-[11px] mt-1 ${active ? "text-gray-300" : "text-[#6B7280]"}`}>
                    {v.weight_grams}g • {v.raw_json_data?.analytics?.total_absorbed_protein_pool_g ? Math.round(v.raw_json_data.analytics.total_absorbed_protein_pool_g / 24) : 30} Servings
                  </div>
                  <div className="mt-2 text-right">
                    <button 
                      onClick={(e) => { e.stopPropagation(); onToggleCompare(v.id, product.brand, v.flavor); }}
                      className={`text-[9px] uppercase font-bold px-2 py-1 border ${compareQueue.find(q => q.variantId === v.id) ? 'bg-emerald-500 text-black border-emerald-500' : 'bg-transparent text-gray-500 border-gray-300 hover:border-black'}`}
                    >
                      {compareQueue.find(q => q.variantId === v.id) ? '✓ Compared' : '+ Compare'}
                    </button>
                  </div>
                </button>"""
content = content.replace(old_variant_button, new_variant_button)

# 7. Add CompareTray and update ProteinTerminal usage in the return statement
old_return_modal = """      {/* Terminal Modal overlay */}
      {selectedProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl border border-[#E5E7EB]">
            {/* Close Button */}
            <div className="sticky top-0 right-0 z-10 flex justify-end bg-transparent p-2 pointer-events-none">
              <button 
                onClick={() => setSelectedProduct(null)}
                className="pointer-events-auto bg-black text-white w-8 h-8 flex items-center justify-center hover:bg-gray-800 font-bold"
              >
                ×
              </button>
            </div>
            <ProteinTerminal product={selectedProduct} onClose={() => setSelectedProduct(null)} />
          </div>
        </div>
      )}"""

new_return_modal = """      {/* Terminal Modal overlay */}
      {selectedProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl border border-[#E5E7EB]">
            {/* Close Button */}
            <div className="sticky top-0 right-0 z-10 flex justify-end bg-transparent p-2 pointer-events-none">
              <button 
                onClick={() => setSelectedProduct(null)}
                className="pointer-events-auto bg-black text-white w-8 h-8 flex items-center justify-center hover:bg-gray-800 font-bold"
              >
                ×
              </button>
            </div>
            <ProteinTerminal 
              product={selectedProduct} 
              onClose={() => setSelectedProduct(null)} 
              compareQueue={compareQueue} 
              onToggleCompare={handleToggleCompare} 
            />
          </div>
        </div>
      )}
      
      <CompareTray 
        queue={compareQueue} 
        onRemove={(id) => handleToggleCompare(id, '', '')} 
        onClear={() => setCompareQueue([])} 
        onCompare={generateSnapshot} 
        isGenerating={isGenerating} 
      />"""
content = content.replace(old_return_modal, new_return_modal)

with open('client/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
