class EqualizerEngine:
    # Based on FAO-recommended clinical digestibility standards
    DIAAS_INDEX = {
        "whey_isolate": 1.09,
        "whey_concentrate": 0.98,
        "casein": 1.18,
        "soy": 0.90,
        "plant_blend": 0.85, # Synergistic Pea + Rice formulation
        "pea_isolate": 0.82,
        "rice_protein": 0.42,
        "whey": 1.0, # Default whey blend
        "plant": 0.85, # Default plant
        "yeast": 0.95
    }

    @classmethod
    def calculate_metrics(
        cls, 
        category: str, 
        price_inr: float, 
        label_protein_g: float, 
        serving_size_g: float, 
        total_servings: int,
        unflavored_cost_per_g: float = None
    ) -> dict:
        # Standardize category key
        cat_key = category.lower().replace(" ", "_")
        diaas = cls.DIAAS_INDEX.get(cat_key, 0.80)
        
        absorbed_protein_per_serving = round(label_protein_g * diaas, 2)
        total_absorbed_protein = absorbed_protein_per_serving * total_servings
        effective_cost_per_g = round(price_inr / total_absorbed_protein, 2) if total_absorbed_protein > 0 else 0.0
        purity_pct = round((label_protein_g / serving_size_g) * 100, 2) if serving_size_g > 0 else 0.0

        flavor_tax_pct = 0.0
        if unflavored_cost_per_g and unflavored_cost_per_g > 0:
            flavor_tax_pct = round(((effective_cost_per_g / unflavored_cost_per_g) - 1.0) * 100, 2)

        return {
            "diaas_score": diaas,
            "absorbed_protein_per_serving_g": absorbed_protein_per_serving,
            "total_absorbed_protein_pool_g": round(total_absorbed_protein, 2),
            "effective_cost_per_bioavailable_g_inr": effective_cost_per_g,
            "scoop_purity_pct": purity_pct,
            "flavor_tax_pct": max(flavor_tax_pct, 0.0)
        }
