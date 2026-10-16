import math
from typing import Any, Dict, Optional

class EqualizerEngine:
    """
    Equalizer Computation Engine
    Compliant with Proteindex PRD v2.1 (Section 3) and Master PRD v3 (Section 6).
    Standardizes all products into absolute unit efficiency metrics.
    Robust against zero values, negative prices, null containers, and extreme inputs.
    """
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

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        if val is None:
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

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
        """
        Original Core Equalizer Metric for Protein Silo
        Preserved with 100% backwards compatibility for existing scraper workers.
        Guarded against negative values, division-by-zero, and extreme prices.
        """
        # Standardize category key
        cat_key = str(category or "").lower().replace(" ", "_")
        diaas = cls.DIAAS_INDEX.get(cat_key, 0.80)
        
        safe_price = max(0.0, cls._safe_float(price_inr, 0.0))
        safe_protein = max(0.0, cls._safe_float(label_protein_g, 0.0))
        safe_serving_size = max(0.0, cls._safe_float(serving_size_g, 0.0))
        safe_servings = max(0, cls._safe_int(total_servings, 0))

        absorbed_protein_per_serving = round(safe_protein * diaas, 2)
        total_absorbed_protein = round(absorbed_protein_per_serving * safe_servings, 2)
        
        effective_cost_per_g = round(safe_price / total_absorbed_protein, 2) if total_absorbed_protein > 0 and safe_price > 0 else 0.0
        
        # Purity cannot exceed 100% (Rule 4 in PRD)
        raw_purity = (safe_protein / safe_serving_size) * 100 if safe_serving_size > 0 else 0.0
        purity_pct = min(100.0, max(0.0, round(raw_purity, 2)))

        flavor_tax_pct = 0.0
        safe_unflavored = cls._safe_float(unflavored_cost_per_g, 0.0) if unflavored_cost_per_g is not None else 0.0
        if safe_unflavored > 0 and effective_cost_per_g > 0:
            flavor_tax_pct = round(((effective_cost_per_g / safe_unflavored) - 1.0) * 100, 2)

        return {
            "diaas_score": diaas,
            "absorbed_protein_per_serving_g": absorbed_protein_per_serving,
            "total_absorbed_protein_pool_g": total_absorbed_protein,
            "effective_cost_per_bioavailable_g_inr": effective_cost_per_g,
            "scoop_purity_pct": purity_pct,
            "flavor_tax_pct": max(flavor_tax_pct, 0.0)
        }

    @classmethod
    def calculate_silo_equalizer(
        cls,
        silo: str,
        price_inr: float,
        packaging: dict,
        nutritional_profile: dict,
        unflavored_price_inr: float = None
    ) -> dict:
        """
        Isolated Category Silos & Equalizer Algorithms (PRD v2.1 Section 3)
        Products from different categories are never mixed. Each silo operates under
        its proprietary Equalizer Metric.
        Fully protected against empty/None dicts, zero calories, zero scoops, and negative values.
        """
        silo_key = str(silo or "protein").lower().replace("-", "_").replace(" ", "_")
        pkg = packaging or {}
        nutr = nutritional_profile or {}

        safe_price = max(0.0, cls._safe_float(price_inr, 0.0))
        
        raw_servings = pkg.get("servingsCount")
        if raw_servings is None:
            raw_servings = pkg.get("total_servings")
        servings = max(1, cls._safe_int(raw_servings, 1))

        raw_size = pkg.get("servingSizeGrams")
        if raw_size is None:
            raw_size = pkg.get("serving_size_g")
        serving_size_g = max(0.0, cls._safe_float(raw_size, 30.0))

        flavor_tax = 0.0
        safe_unflavored_price = cls._safe_float(unflavored_price_inr, 0.0) if unflavored_price_inr is not None else 0.0
        if safe_unflavored_price > 0 and safe_price > safe_unflavored_price:
            flavor_tax = round(((safe_price / safe_unflavored_price) - 1.0) * 100, 2)

        if silo_key in ("protein", "whey", "plant", "casein"):
            # Silo 1: Protein Powders
            # Primary: ₹ / g of Bioavailable Protein = Price / (Servings * Protein per Serving * DIAAS)
            # Secondary: Purity (%) = (Protein per Serving / Serving Size) * 100
            raw_prot = nutr.get("proteinPerServingGrams")
            if raw_prot is None:
                raw_prot = nutr.get("activeIngredientPerServingGrams")
            protein_g = max(0.0, cls._safe_float(raw_prot, 24.0))
            subcat = str(nutr.get("subCategory", "whey")).lower().replace(" ", "_")
            diaas = cls.DIAAS_INDEX.get(subcat, 1.0)
            
            bioavailable_protein = round(protein_g * diaas, 2)
            total_bioavailable = bioavailable_protein * servings
            cost_per_g = round(safe_price / total_bioavailable, 2) if total_bioavailable > 0 and safe_price > 0 else 0.0
            
            raw_purity = (protein_g / serving_size_g) * 100 if serving_size_g > 0 else 0.0
            purity = min(100.0, max(0.0, round(raw_purity, 2)))

            res = {
                "primaryMetricLabel": "₹/g bioavailable protein",
                "primaryMetricValue": cost_per_g,
                "secondaryMetricLabel": "Purity %",
                "secondaryMetricValue": purity,
                "diaasScore": diaas,
                "bioavailableProteinPerServing": bioavailable_protein
            }
            if safe_unflavored_price > 0:
                res["flavorTaxPct"] = max(flavor_tax, 0.0)
            return res

        elif silo_key in ("mass_gainers", "mass_gainer", "gainer"):
            # Silo 2: Mass Gainers
            # Core Metric: (Price ÷ Total Calories in Tub) × 1000 (₹ per 1,000 kcal)
            # Secondary Metric: Carbs per Serving (g) ÷ Protein per Serving (g)
            cals_per_serving = max(0.0, cls._safe_float(nutr.get("caloriesPerServing"), 350.0))
            total_cals = cals_per_serving * servings
            cost_per_1000_kcal = round((safe_price / total_cals) * 1000, 2) if total_cals > 0 and safe_price > 0 else 0.0
            
            carbs_g = max(0.0, cls._safe_float(nutr.get("carbsPerServingGrams"), 70.0))
            protein_g = max(0.0, cls._safe_float(nutr.get("proteinPerServingGrams"), 20.0))
            carb_protein_ratio = round(carbs_g / protein_g, 2) if protein_g > 0 else 0.0

            res = {
                "primaryMetricLabel": "₹/1,000 kcal",
                "primaryMetricValue": cost_per_1000_kcal,
                "secondaryMetricLabel": "Carb:Protein Ratio",
                "secondaryMetricValue": carb_protein_ratio,
                "totalCalories": total_cals
            }
            if safe_unflavored_price > 0:
                res["flavorTaxPct"] = max(flavor_tax, 0.0)
            return res

        elif silo_key in ("creatine", "creatine_monohydrate"):
            # Silo 3: Creatine
            # Core Metric: Price ÷ (Servings × Creatine per Serving) (₹ / g of pure Creatine)
            creatine_g = max(0.0, cls._safe_float(nutr.get("activeIngredientPerServingGrams"), 3.0))
            total_creatine = creatine_g * servings
            cost_per_g_creatine = round(safe_price / total_creatine, 2) if total_creatine > 0 and safe_price > 0 else 0.0

            res = {
                "primaryMetricLabel": "₹/g pure Creatine",
                "primaryMetricValue": cost_per_g_creatine,
                "secondaryMetricLabel": "Creatine per Scoop (g)",
                "secondaryMetricValue": creatine_g,
                "totalCreatineGrams": total_creatine
            }
            if safe_unflavored_price > 0:
                res["flavorTaxPct"] = max(flavor_tax, 0.0)
            return res

        elif silo_key in ("pre_workout", "preworkout"):
            # Silo 4: Pre-Workout
            # Core Metric: Price ÷ Total Full Scoops (₹ / Standardized Serving)
            cost_per_scoop = round(safe_price / servings, 2) if servings > 0 and safe_price > 0 else 0.0
            caffeine_mg = max(0.0, cls._safe_float(nutr.get("caffeinePerServingMg"), 200.0))

            res = {
                "primaryMetricLabel": "₹/standard scoop",
                "primaryMetricValue": cost_per_scoop,
                "secondaryMetricLabel": "Caffeine per Scoop (mg)",
                "secondaryMetricValue": caffeine_mg,
                "totalScoops": servings
            }
            if safe_unflavored_price > 0:
                res["flavorTaxPct"] = max(flavor_tax, 0.0)
            return res

        elif silo_key in ("snacks", "snack", "protein_snacks"):
            # Silo 5: Protein Snacks (Wafers, Bars, Cookies, Brownies, Granola)
            # Primary: Price per 100g = (safe_price / total_weight_g) * 100
            total_weight_g = max(0.0, cls._safe_float(pkg.get("weight_grams") or (serving_size_g * servings), 100.0))
            cost_per_100g = round((safe_price / total_weight_g) * 100, 2) if total_weight_g > 0 and safe_price > 0 else 0.0
            raw_prot = nutr.get("proteinPerServingGrams") or nutr.get("activeIngredientPerServingGrams")
            protein_g = max(0.0, cls._safe_float(raw_prot, 10.0))

            res = {
                "primaryMetricLabel": "₹/100g",
                "primaryMetricValue": cost_per_100g,
                "secondaryMetricLabel": "Protein/Serving (g)",
                "secondaryMetricValue": protein_g,
                "totalWeightGrams": total_weight_g
            }
            if safe_unflavored_price > 0:
                res["flavorTaxPct"] = max(flavor_tax, 0.0)
            return res

        else:
            # Default fallback to standard protein metric
            return cls.calculate_silo_equalizer("protein", safe_price, pkg, nutr, unflavored_price_inr=unflavored_price_inr)
