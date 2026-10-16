import os
import sys
import json
from typing import Dict, List, Any, Optional
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Force UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add parent directories to sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from trust_safety.amino_spiking_rules import AminoSpikingRulesEngine

class AminoSpikingAgent:
    """
    Proteindex Autonomous Amino Spiking Rules Agent
    Periodically scans catalog products in Supabase, analyzes ingredient
    profiles for artificial nitrogen spiking, adjusts trust scores,
    and isolates high-risk products into the quarantine ledger.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.supabase = None
        self._init_supabase()

    def _init_supabase(self):
        if load_dotenv:
            load_dotenv(os.path.join(SRC_DIR, "..", "..", ".env"))
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                self.supabase = create_client(supabase_url, supabase_key)
            except Exception as e:
                print(f"[AminoSpikingAgent] Warning: Supabase client init failed ({e}). Running in dry-run mode.")
                self.dry_run = True
        else:
            self.dry_run = True

    def audit_product(self, product: Dict[str, Any], variants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Audits a single product and its variants for amino spiking deception.
        """
        ingredients = product.get("nutrition_ingredients") or ""
        
        # Also inspect variants for declared leucine or raw ingredient panel
        declared_leucine = None
        for v in variants:
            raw_data = v.get("raw_json_data")
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception:
                    raw_data = {}
            if isinstance(raw_data, dict):
                declared_leucine = raw_data.get("leucine_g") or raw_data.get("usefulDoseAnalysis", {}).get("leucinePerServingGrams")
                if declared_leucine:
                    break

        eval_result = AminoSpikingRulesEngine.evaluate(
            raw_ingredients=ingredients,
            declared_protein_g=product.get("nutrition_protein_per_serving_g") or 24.0,
            declared_leucine_g=declared_leucine,
            serving_size_g=product.get("nutrition_serving_size_g") or 30.0,
            category=product.get("category_silo") or "protein"
        )

        return eval_result

    def run(self) -> Dict[str, Any]:
        """
        Executes audit over all active protein supplements in catalog.
        """
        print("=" * 65)
        print("PROTEINDEX AMINO SPIKING AUDIT AGENT")
        print(f"Mode: {'DRY RUN (No database mutations)' if self.dry_run else 'LIVE ENFORCEMENT'}")
        print("=" * 65)

        if not self.supabase:
            print("[AminoSpikingAgent] No Supabase connection available. Running offline test verification...")
            test_prods = [
                {
                    "id": "mock-prod-001",
                    "brand": "SpikeBrand",
                    "base_name": "Ultra Whey 100% Protein",
                    "category_silo": "protein",
                    "nutrition_ingredients": "Whey Protein Concentrate, Glycine, L-Taurine, Creatine Monohydrate",
                    "nutrition_protein_per_serving_g": 24.0,
                    "trust_score": 100
                },
                {
                    "id": "mock-prod-002",
                    "brand": "CleanNutrition",
                    "base_name": "Pure Gold Isolate",
                    "category_silo": "protein",
                    "nutrition_ingredients": "Whey Protein Isolate, Cocoa Powder, Sunflower Lecithin, Stevia",
                    "nutrition_protein_per_serving_g": 27.0,
                    "trust_score": 100
                }
            ]
            results = []
            for p in test_prods:
                res = self.audit_product(p, [])
                results.append({"product": p["base_name"], "audit": res})
                print(f"Product: {p['base_name']} -> {res['badge']} (Risk: {res['riskLevel']}, Deduction: -{res['trustDeduction']})")
            return {"status": "SUCCESS", "scanned": len(test_prods), "results": results}

        # Fetch protein catalog
        print("Fetching protein products from database...")
        res = self.supabase.table("products").select(
            "id, brand, base_name, category_silo, nutrition_ingredients, nutrition_protein_per_serving_g, nutrition_serving_size_g, trust_score, fairy_dusting_flags"
        ).in_("category_silo", ["protein", "whey", "isolate", "concentrate"]).execute()
        
        products = res.data or []
        print(f"Auditing {len(products)} protein products...")

        scanned = 0
        confirmed_spiked = 0
        suspected_spiked = 0
        clean_count = 0

        for p in products:
            scanned += 1
            v_res = self.supabase.table("variants").select("id, raw_json_data").eq("product_id", p["id"]).execute()
            variants = v_res.data or []

            audit_res = self.audit_product(p, variants)
            risk = audit_res["riskLevel"]

            if risk == "CONFIRMED_SPIKED":
                confirmed_spiked += 1
                print(f"  [CRITICAL SPIKE] {p['brand']} - {p['base_name']}: {audit_res['summary']}")
                if not self.dry_run:
                    # Deduct trust score
                    current_trust = p.get("trust_score") or 100
                    new_trust = max(10, current_trust - audit_res["trustDeduction"])
                    existing_flags = p.get("fairy_dusting_flags") or []
                    updated_flags = list(set(existing_flags + [audit_res["summary"]]))

                    self.supabase.table("products").update({
                        "trust_score": new_trust,
                        "is_fairy_dusted": True,
                        "fairy_dusting_flags": updated_flags
                    }).eq("id", p["id"]).execute()

                    # Quarantine logging
                    self.supabase.table("staging_quarantine").insert({
                        "platform": "amino_spiking_agent",
                        "brand_hint": p.get("brand"),
                        "raw_title": p.get("base_name"),
                        "failure_category": "AMINO_SPIKED",
                        "details": audit_res
                    }).execute()

            elif risk == "SUSPECTED_SPIKING":
                suspected_spiked += 1
                print(f"  [SUSPECTED] {p['brand']} - {p['base_name']}: {audit_res['summary']}")
                if not self.dry_run:
                    current_trust = p.get("trust_score") or 100
                    new_trust = max(30, current_trust - audit_res["trustDeduction"])
                    self.supabase.table("products").update({
                        "trust_score": new_trust
                    }).eq("id", p["id"]).execute()

            else:
                clean_count += 1

        summary = {
            "status": "COMPLETED",
            "total_scanned": scanned,
            "confirmed_spiked": confirmed_spiked,
            "suspected_spiked": suspected_spiked,
            "clean_count": clean_count
        }
        print("-" * 65)
        print(f"Summary: {scanned} scanned | {confirmed_spiked} confirmed spiked | {suspected_spiked} suspected | {clean_count} clean")
        print("=" * 65)
        return summary

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or "--live" not in sys.argv
    agent = AminoSpikingAgent(dry_run=dry)
    agent.run()
