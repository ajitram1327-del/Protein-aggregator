import sys
import json
import logging
from pydantic import ValidationError

# Ensure Windows console handles UTF-8 gracefully without charmap/cp1252 exceptions
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure your local source paths are reachable by the runtime env
sys.path.append(".") 

from src.analytics.equalizer import EqualizerEngine
from scraper.scrapling_scraper.src.scraper.sanitizer import extract_normalized_grams

# Setup high-visibility tracing logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HardDataFlowChecker")

class HardFlowTester:
    def __init__(self):
        self.failures_found = 0

    def assert_test(self, condition: bool, error_message: str):
        if not condition:
            self.failures_found += 1
            print(f"❌ INTEGRITY BREAKDOWN: {error_message}")
        else:
            print("  ✅ Passed structural condition.")

    def run_destructive_suite(self):
        print("\n=========================================================")
        print("⚡ INITIATING REAL-WORLD ADVERSARIAL INTEGRITY INSPECTION ⚡")
        print("=========================================================\n")

        # -----------------------------------------------------------------
        # TEST 1: The Context Clashing Text Trap (The RiteBite Blended Variant Case)
        # -----------------------------------------------------------------
        print("[Insepction 1] Testing Text-Stripping Logic Against Multi-Metric Title Noise...")
        raw_noisy_title = "RiteBite Max Protein Plant 2kg Choco Almond with 5g BCAAs, 3000mg Glutamine and Free Shaker"
        
        # Act
        parsed_grams = extract_normalized_grams(title=raw_noisy_title)
        
        # Assert: If your parser catches '5g BCAAs' or '3000mg' instead of '2kg', it fails
        self.assert_test(
            parsed_grams == 2000,
            f"Sanitizer swallowed micro-additives! Expected 2000g, but script returned: {parsed_grams}g"
        )

        # -----------------------------------------------------------------
        # TEST 2: The Textual Multi-Pack Mapping Check
        # -----------------------------------------------------------------
        print("\n[Insepction 2] Testing Word-to-Digit Conversion Loops...")
        word_pack_title = "As-It-Is Raw Whey Protein Twin Pack (Two 1kg Tubs)"
        
        # Act
        parsed_twin_grams = extract_normalized_grams(title=word_pack_title)
        
        # Assert: A 'Twin Pack' of 'Two 1kg Tubs' must evaluate to 2000g, not 1000g or None
        self.assert_test(
            parsed_twin_grams == 2000,
            f"Multi-pack word extractor failed! Expected 2000g, but script returned: {parsed_twin_grams}g"
        )

        # -----------------------------------------------------------------
        # TEST 3: The Hard Biological Ceiling Check (The 120% Purity Hallucination)
        # -----------------------------------------------------------------
        print("\n[Insepction 3] Testing Mathematical Conservation of Mass...")
        # Scenario: OCR crosses columns and reports 32g of protein inside a 30g scoop
        bad_ocr_protein = 32.0
        bad_ocr_scoop = 30.0
        mock_price = 2499.0
        mock_servings = 33
        
        # Act & Assert
        try:
            metrics = EqualizerEngine.calculate_metrics(
                category="protein",
                price_inr=mock_price,
                label_protein_g=bad_ocr_protein,
                serving_size_g=bad_ocr_scoop,
                total_servings=mock_servings
            )
            # If the code reaches this line without throwing an exception, your guardrails are failing
            self.failures_found += 1
            print(f"❌ CRITICAL MATHEMATICAL FAILURE: EqualizerEngine allowed an impossible purity calculation! Returned: {metrics['scoop_purity_pct']}%")
        except ValueError as e:
            print(f"  ✅ Passed: Engine successfully blocked impossible math. Caught error: {e}")
        except Exception as e:
            self.failures_found += 1
            print(f"❌ UNEXPECTED CRASH: Engine threw a general exception instead of a clean ValueError: {e}")

        # -----------------------------------------------------------------
        # TEST 4: The Out-of-Bounds Biological Filtering Audit
        # -----------------------------------------------------------------
        print("\n[Insepction 4] Testing Processing Ceiling Threshold Checks...")
        # Scenario: OCR reads 29.5g protein in a 30g scoop (98.3% purity). Natural whey isolates top out at 90-93%.
        impossible_purity_protein = 29.5
        valid_scoop = 30.0

        try:
            metrics = EqualizerEngine.calculate_metrics(
                category="protein",
                price_inr=mock_price,
                label_protein_g=impossible_purity_protein,
                serving_size_g=valid_scoop,
                total_servings=mock_servings
            )
            self.failures_found += 1
            print(f"❌ CRITICAL BIREAKDOWN: EqualizerEngine accepted an impossible purity score of {metrics['scoop_purity_pct']}% for natural whey.")
        except ValueError as e:
            print(f"  ✅ Passed: Engine caught chemical anomaly. Caught error: {e}")

        # -----------------------------------------------------------------
        # FINAL MATRIX VERIFICATION EVALUATION
        # -----------------------------------------------------------------
        print("\n=========================================================")
        if self.failures_found > 0:
            print(f"🚨 INTEGRITY AUDIT FAILED: Found {self.failures_found} unhandled data anomalies.")
            print("Your code contains active logic leaks that are corrupting your live data views.")
        else:
            print("💎 CATALOG INTEGRITY SECURED: Zero data leaks found.")
            print("Your data normalization layers match real-world constraints.")
        print("=========================================================\n")

if __name__ == "__main__":
    tester = HardFlowTester()
    tester.run_destructive_suite()
