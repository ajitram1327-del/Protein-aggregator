import re
from typing import Dict, List, Optional, Any, Tuple

class AminoSpikingRulesEngine:
    """
    Dedicated Amino Spiking Rules Engine (Proteindex PRD v2.1 & v3 Section 4).
    Evaluates protein powder ingredient statements, amino acid profiles,
    and leucine-to-protein ratios to detect nitrogen-spiking deception.
    
    Mechanisms Analyzed:
    1. Free-form non-proteinogenic amino acids & cheap nitrogen donors (Glycine, Taurine, Creatine, Alanine).
    2. Undisclosed amino complexes ('Amino Matrix', 'Recovery Blend') inflating nitrogen test assays (Kjeldahl/Dumas).
    3. Leucine threshold vs Muscle Protein Synthesis (MPS) minimum (~2.5g - 3.0g).
    4. Leucine-to-protein ratio (Natural intact whey = 10-12%; < 8% indicates cut/diluted protein).
    """

    # Primary free-form amino acids used for artificial nitrogen boosting
    FREE_FORM_SPIKING_AGENTS = [
        "glycine", "l-glycine",
        "taurine", "l-taurine",
        "creatine", "creatine monohydrate", "buffered creatine",
        "l-glutamine", "glutamine", "glutamine peptides",
        "alanine", "l-alanine", "beta-alanine",
        "l-proline", "proline", "hydroxyproline",
        "l-arginine", "arginine", "arginine akg",
        "l-methionine", "methionine",
        "betaine", "betaine anhydrous"
    ]

    # Non-protein nitrogen chemicals
    SYNTHETIC_NITROGEN_COMPOUNDS = [
        "melamine", "cyanuric acid", "urea", "ammonium sulfate", "ammonium chloride"
    ]

    # Proprietary / opaque amino matrices designed to obscure true protein content
    OPAQUE_AMINO_BLENDS = [
        r"\bamino\s*(?:matrix|complex|blend|retention|fusion|stack)\b",
        r"\bnitrogen\s*(?:retention|boost|matrix|complex)\b",
        r"\bprotein\s*(?:plus|enhancer|booster)\s*matrix\b",
        r"\brecovery\s*(?:amino|matrix|complex)\b"
    ]

    # Intact, legitimate protein bases
    INTACT_PROTEIN_BASES = [
        "whey protein isolate", "whey isolate",
        "whey protein concentrate", "whey concentrate",
        "hydrolyzed whey", "hydrolyzed whey protein",
        "micellar casein", "calcium caseinate",
        "milk protein isolate", "milk protein concentrate",
        "egg white protein", "pea protein isolate",
        "brown rice protein", "soy protein isolate"
    ]

    @classmethod
    def evaluate(
        cls,
        raw_ingredients: Optional[str],
        declared_protein_g: Optional[float] = 24.0,
        declared_leucine_g: Optional[float] = None,
        serving_size_g: Optional[float] = 30.0,
        category: Optional[str] = "protein"
    ) -> Dict[str, Any]:
        """
        Executes comprehensive amino-spiking audit against supplied formulation data.
        Returns risk classification, detected agents, MPS score, and trust deductions.
        """
        ing_text = (raw_ingredients or "").lower()
        clean_text = re.sub(r"[^\w\s\-\,]", " ", ing_text)

        detected_spiking_agents: List[str] = []
        detected_synthetic_compounds: List[str] = []
        opaque_blends_found: List[str] = []
        
        # 1. Search for free-form amino acids
        for agent in cls.FREE_FORM_SPIKING_AGENTS:
            # Word-boundary check to prevent partial matches
            if re.search(rf"\b{re.escape(agent)}\b", clean_text):
                detected_spiking_agents.append(agent)

        # 2. Search for synthetic nitrogen adulterants (Critical Severity)
        for compound in cls.SYNTHETIC_NITROGEN_COMPOUNDS:
            if re.search(rf"\b{re.escape(compound)}\b", clean_text):
                detected_synthetic_compounds.append(compound)

        # 3. Search for opaque amino blends
        for pattern in cls.OPAQUE_AMINO_BLENDS:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                opaque_blends_found.append(match.group(0))

        # 4. Check positioning relative to primary protein source
        early_spiking_flags: List[str] = []
        tokens = [t.strip() for t in re.split(r"[,|\n]", clean_text) if t.strip()]
        for idx, token in enumerate(tokens[:5]): # Check top 5 ingredients
            for agent in detected_spiking_agents:
                if agent in token:
                    early_spiking_flags.append(f"Spiking agent '{agent}' listed prominently at ingredient position #{idx + 1}")

        # 5. Leucine & MPS Threshold Evaluation
        protein_g = max(1.0, float(declared_protein_g or 24.0))
        
        # If leucine not explicitly stated, estimate baseline for natural intact whey (~10.5%)
        # But if spiking agents are detected, discount effective leucine
        if declared_leucine_g is not None and declared_leucine_g > 0:
            effective_leucine = float(declared_leucine_g)
            is_leucine_estimated = False
        else:
            if len(detected_spiking_agents) > 0 or len(detected_synthetic_compounds) > 0:
                # Spiked protein has diluted genuine leucine
                effective_leucine = round(protein_g * 0.065, 2)
            else:
                effective_leucine = round(protein_g * 0.108, 2)
            is_leucine_estimated = True

        leucine_ratio_pct = round((effective_leucine / protein_g) * 100, 1)
        
        # MPS Threshold: >= 2.5g leucine AND intact protein source
        meets_mps = (effective_leucine >= 2.5) and (len(detected_spiking_agents) == 0) and (len(detected_synthetic_compounds) == 0)

        # 6. Risk Level & Trust Deduction Determination
        if len(detected_synthetic_compounds) > 0:
            risk_level = "CONFIRMED_SPIKED"
            badge = "⚠️ Adulterated Nitrogen Spiking"
            trust_deduction = 100
            quarantine = True
            summary = f"Dangerous non-protein nitrogen compounds detected: {', '.join(detected_synthetic_compounds)}"

        elif len(detected_spiking_agents) >= 2 or len(early_spiking_flags) > 0:
            risk_level = "CONFIRMED_SPIKED"
            badge = "⚠️ High Amino Spiking Risk"
            trust_deduction = 45
            quarantine = True
            summary = f"Free-form amino acids ({', '.join(detected_spiking_agents)}) detected inflating declared protein"

        elif len(detected_spiking_agents) == 1:
            risk_level = "SUSPECTED_SPIKING"
            badge = "⚠️ Added Free-Form Aminos"
            trust_deduction = 25
            quarantine = False
            summary = f"Added free-form '{detected_spiking_agents[0]}' detected; verify third-party amino acid profile"

        elif len(opaque_blends_found) > 0 or (leucine_ratio_pct < 8.0 and not is_leucine_estimated):
            risk_level = "SUSPECTED_SPIKING"
            badge = "⚠️ Suspected Nitrogen Matrix"
            trust_deduction = 20
            quarantine = False
            summary = f"Opaque amino matrix or low leucine ratio ({leucine_ratio_pct}%) detected"

        else:
            risk_level = "CLEAN"
            badge = "✓ Clean Amino Profile"
            trust_deduction = 0
            quarantine = False
            summary = "Intact protein profile without artificial nitrogen spiking agents"

        return {
            "riskLevel": risk_level,
            "aminoSpikeRisk": risk_level in ("CONFIRMED_SPIKED", "SUSPECTED_SPIKING"),
            "badge": badge,
            "trustDeduction": trust_deduction,
            "quarantineRecommended": quarantine,
            "detectedAgents": detected_spiking_agents,
            "detectedSyntheticCompounds": detected_synthetic_compounds,
            "opaqueBlendsFound": opaque_blends_found,
            "earlySpikingFlags": early_spiking_flags,
            "summary": summary,
            "mpsAnalysis": {
                "leucinePerServingGrams": round(effective_leucine, 2),
                "leucineToProteinRatioPct": leucine_ratio_pct,
                "meetsMpsThreshold": meets_mps,
                "isLeucineEstimated": is_leucine_estimated
            }
        }
