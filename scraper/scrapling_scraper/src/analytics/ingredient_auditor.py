import re
from typing import List, Dict, Any

class IngredientAuditor:
    """
    Ingredient and Formulation Safety Auditor
    Compliant with Proteindex PRD v2.1 (Section 4) and Master PRD v3 (Section 10.1).
    Detects proprietary blend deception (fairy dusting), amino spiking, and MPS leucine thresholds.
    """

    # Fillers often fairy-dusted or used as cheap bulking agents
    FILLERS = [
        "maltodextrin", "taurine", "glycine", "creatine monohydrate", 
        "dextrose", "sucrose", "sugar", "fructose", "corn syrup", "thickener", "xanthan gum"
    ]
    
    # Premium actives that brands market prominently
    ACTIVES = [
        "whey protein isolate", "whey isolate", "bcaa", "l-citrulline",
        "citrulline malate", "hydrolyzed whey", "micellar casein"
    ]

    # Added free-form amino acids indicative of nitrogen/amino spiking in protein powders
    AMINO_SPIKING_AGENTS = [
        "glycine", "l-glycine", "taurine", "l-taurine",
        "glutamine", "l-glutamine", "creatine", "creatine monohydrate"
    ]

    @classmethod
    def audit(cls, raw_ingredients: str) -> dict:
        """
        Baseline Fairy-Dusting Check (PRD Section 10.1).
        Flags products where cheap fillers are listed before premium actives.
        """
        if not raw_ingredients:
            return {"is_fairy_dusted": False, "flags": [], "trust_deduction": 0}
            
        ingredients = [i.strip().lower() for i in re.split(r'[,|\[\]\(\)]', raw_ingredients) if i.strip()]
        
        flags = []
        deduction = 0
        
        # Check relative positions (FSSAI requires descending order by weight)
        for filler in cls.FILLERS:
            try:
                filler_idx = next(i for i, v in enumerate(ingredients) if filler in v)
            except StopIteration:
                continue
                
            for active in cls.ACTIVES:
                try:
                    active_idx = next(i for i, v in enumerate(ingredients) if active in v)
                except StopIteration:
                    continue
                    
                # If filler appears BEFORE active ingredient, it's fairy dusting
                if filler_idx < active_idx:
                    flags.append(f"Cheap filler '{filler}' listed before premium active '{active}'")
                    deduction += 15
        
        flags = list(set(flags))
        
        return {
            "is_fairy_dusted": len(flags) > 0,
            "flags": flags,
            "trust_deduction": deduction
        }

    @classmethod
    def audit_useful_dose(cls, raw_ingredients: str, leucine_g: float = None, is_protein_powder: bool = True) -> dict:
        """
        Useful Dose & Bioavailability Engine (PRD v2.1 Section 4).
        Evaluates physiological utility:
        1. Leucine Threshold: Flags products that meet the ~2.5g-3.0g MPS threshold.
        2. Amino Spiking Detection: Flags added free-form amino acids in protein powders.
        """
        ing_text = (raw_ingredients or "").lower()
        fillers_detected = []
        spiking_agents_found = []

        # Find fillers
        for f in cls.FILLERS:
            if re.search(rf"\b{re.escape(f)}\b", ing_text):
                fillers_detected.append(f)

        # Find amino spiking agents if protein powder
        if is_protein_powder:
            for agent in cls.AMINO_SPIKING_AGENTS:
                if re.search(rf"\b{re.escape(agent)}\b", ing_text):
                    spiking_agents_found.append(agent)

        amino_spike_risk = len(spiking_agents_found) > 0
        
        # Default leucine estimation if not explicitly parsed from label
        estimated_leucine = leucine_g if (leucine_g is not None and leucine_g > 0) else 2.6
        meets_mps = estimated_leucine >= 2.5 and not amino_spike_risk

        # Extended rules evaluation if module available
        try:
            from trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
            rules_eval = AminoSpikingRulesEngine.evaluate(
                raw_ingredients=raw_ingredients,
                declared_leucine_g=leucine_g,
                category="protein" if is_protein_powder else "general"
            )
        except Exception:
            rules_eval = {
                "riskLevel": "CONFIRMED_SPIKED" if amino_spike_risk else "CLEAN",
                "badge": "⚠️ High Amino Spiking Risk" if amino_spike_risk else "✓ Clean Amino Profile",
                "trustDeduction": 45 if amino_spike_risk else 0,
                "quarantineRecommended": amino_spike_risk
            }

        return {
            "leucinePerServingGrams": round(estimated_leucine, 2),
            "meetsMpsThreshold": meets_mps,
            "aminoSpikeRisk": amino_spike_risk,
            "spikingAgents": spiking_agents_found,
            "fillersDetected": fillers_detected,
            "riskLevel": rules_eval.get("riskLevel", "CONFIRMED_SPIKED" if amino_spike_risk else "CLEAN"),
            "badge": rules_eval.get("badge", "⚠️ High Amino Spiking Risk" if amino_spike_risk else "✓ Clean Amino Profile"),
            "trustDeduction": rules_eval.get("trustDeduction", 45 if amino_spike_risk else 0),
            "quarantineRecommended": rules_eval.get("quarantineRecommended", amino_spike_risk),
            "summary": rules_eval.get("summary", "Amino acid audit complete")
        }
