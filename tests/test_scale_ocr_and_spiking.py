"""
tests/test_scale_ocr_and_spiking.py
Comprehensive Verification Suite:
1. Spatial OCR Row-Bounding-Box: Correctly picks 24g from "Per 32g Serving" column instead of 75g from "Per 100g" column.
2. OCR Decimal Auto-Correction: 240g protein in a 30g scoop -> 24.0g.
3. Atwater Calorie & Physics Rejection: Violations in conservation of mass / Atwater thermodynamics get rejected.
4. Amino-Spiking Telemetry Extraction: Detects added Glycine/Taurine/Creatine, computes leucine-to-protein ratio and true unspiked protein.
5. Cross-Dimensional Variant Unification: 30 Servings listing with no weight bridges to 907g Master Variant via OCR serving_size_g = 30.2g.
6. 10,000-Candidate Canopy Index Lookup Benchmark: < 2.0 seconds.
"""

import sys
import os
import time
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
SCRAPER_DIR = os.path.join(BASE_DIR, 'scraper', 'scrapling_scraper')
if SCRAPER_DIR not in sys.path:
    sys.path.insert(0, SCRAPER_DIR)
if os.path.join(SCRAPER_DIR, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(SCRAPER_DIR, 'src'))

from src.pipeline.catalog_taxonomy import (
    StatefulTitleParser,
    snap_to_canonical_weight,
    is_economically_valid_price,
    generate_blocking_key,
    generate_canopy_key
)
from src.pipeline.nutrition_ocr_pipeline import (
    BoundingBoxWord,
    SpatialRowBoundingBoxParser,
    AtwaterThermodynamicValidator,
    NutritionFactsPayload,
    PerceptualHashDeduplicator
)
from pipeline.matcher import MasterCatalogMatcher


class TestScaleOCRAndSpiking(unittest.TestCase):

    def test_01_spatial_ocr_column_coordinate_resolution(self):
        """
        Verify spatial bounding box OCR parser correctly extracts 24g from 'Per Serving' column
        and does NOT get trapped by 75g in 'Per 100g' column.
        """
        words = [
            # Header Row
            BoundingBoxWord("Nutritional", 10, 10, 80, 25),
            BoundingBoxWord("Facts", 85, 10, 130, 25),
            # Column headers: Per Serving (X: 130..170) vs Per 100g (X: 250..290)
            BoundingBoxWord("Per", 130, 30, 150, 45),
            BoundingBoxWord("Serving", 155, 30, 200, 45),
            BoundingBoxWord("Per", 250, 30, 270, 45),
            BoundingBoxWord("100g", 275, 30, 310, 45),
            # Sizing Row
            BoundingBoxWord("Serving", 10, 50, 60, 65),
            BoundingBoxWord("Size:", 65, 50, 100, 65),
            BoundingBoxWord("32g", 140, 50, 165, 65),
            # Protein Row: 24g under Per Serving, 75g under Per 100g
            BoundingBoxWord("Protein", 10, 70, 60, 85),
            BoundingBoxWord("24g", 140, 70, 165, 85),
            BoundingBoxWord("75g", 260, 70, 285, 85),
            # Energy Row: 120 kcal vs 375 kcal
            BoundingBoxWord("Energy", 10, 90, 55, 105),
            BoundingBoxWord("120", 140, 90, 165, 105),
            BoundingBoxWord("375", 260, 90, 285, 105),
            # Carbohydrates Row: 3.0g vs 9.4g
            BoundingBoxWord("Carbohydrates", 10, 110, 90, 125),
            BoundingBoxWord("3.0g", 140, 110, 170, 125),
            BoundingBoxWord("9.4g", 260, 110, 290, 125),
            # Fat Row: 1.5g vs 4.7g
            BoundingBoxWord("Fat", 10, 130, 35, 145),
            BoundingBoxWord("1.5g", 140, 130, 165, 145),
            BoundingBoxWord("4.7g", 260, 130, 285, 145),
        ]

        payload = SpatialRowBoundingBoxParser.parse_bounding_boxes(words)

        self.assertEqual(payload.serving_size_g, 32.0)
        self.assertEqual(payload.protein_per_serving_g, 24.0, "Must be 24g from Per Serving, NOT 75g from Per 100g!")
        self.assertEqual(payload.per_100g_protein, 75.0)
        self.assertEqual(payload.energy_kcal, 120.0)
        self.assertEqual(payload.per_100g_energy, 375.0)

        is_valid, notes = AtwaterThermodynamicValidator.validate_and_correct(payload)
        self.assertTrue(is_valid, f"Physics validation failed: {notes}")

    def test_02_decimal_auto_correction(self):
        """
        Verify OCR decimal misread auto-correction: 240g protein in 30g scoop -> 24.0g.
        """
        payload = NutritionFactsPayload(
            serving_size_g=30.0,
            servings_per_container=33,
            energy_kcal=120.0,
            protein_per_serving_g=240.0,  # Corrupted decimal
            carbs_per_serving_g=2.0,
            fat_per_serving_g=1.5
        )

        is_valid, notes = AtwaterThermodynamicValidator.validate_and_correct(payload)
        self.assertTrue(is_valid)
        self.assertEqual(payload.protein_per_serving_g, 24.0)
        self.assertTrue(any("Auto-corrected protein decimal" in n for n in notes))

    def test_03_atwater_physics_violation_rejection(self):
        """
        Verify that corrupted OCR reads that violate thermodynamics are strictly rejected.
        """
        # Conservation of mass violation: protein (28g) + carbs (10g) + fat (5g) = 43g > 30g scoop!
        corrupt_payload = NutritionFactsPayload(
            serving_size_g=30.0,
            servings_per_container=30,
            energy_kcal=120.0,
            protein_per_serving_g=28.0,
            carbs_per_serving_g=10.0,
            fat_per_serving_g=5.0
        )
        is_valid, notes = AtwaterThermodynamicValidator.validate_and_correct(corrupt_payload)
        self.assertFalse(is_valid)
        self.assertTrue(any("Conservation of mass violated" in n for n in notes))

        # Atwater calorie discrepancy violation: 24g prot (96kcal) + 2g carb (8kcal) + 1g fat (9kcal) = 113kcal, declared = 350kcal (> 15% diff)
        corrupt_energy = NutritionFactsPayload(
            serving_size_g=30.0,
            servings_per_container=30,
            energy_kcal=350.0,  # Wildly mismatched calories
            protein_per_serving_g=24.0,
            carbs_per_serving_g=2.0,
            fat_per_serving_g=1.0
        )
        is_valid2, notes2 = AtwaterThermodynamicValidator.validate_and_correct(corrupt_energy)
        self.assertFalse(is_valid2)
        self.assertTrue(any("Atwater calorie discrepancy" in n for n in notes2))

    def test_04_amino_spiking_payload_extraction(self):
        """
        Verify detection of added free-form Glycine/Taurine/Creatine inside a Whey label,
        computation of leucine_to_protein_ratio, spiking nitrogen delta, and true unspiked protein.
        """
        label_text = """
        SUPPLEMENT FACTS
        Serving Size: 35g
        Servings Per Container: 30
        Calories: 130 kcal
        Protein: 25g
        Total Carbohydrates: 3g
        Fat: 1.5g
        L-Leucine: 1.8g
        L-Isoleucine: 1.0g
        L-Valine: 1.0g
        Total BCAAs: 3.8g
        Creatine Monohydrate: 3.0g
        L-Glycine: 2.0g
        Taurine: 1.0g
        Ingredients: Whey Protein Concentrate, Added L-Glycine, Taurine, Creatine Monohydrate, Cocoa, Sucralose.
        """
        payload = SpatialRowBoundingBoxParser._parse_raw_text(label_text)
        is_valid, notes = AtwaterThermodynamicValidator.validate_and_correct(payload)
        self.assertTrue(is_valid)

        self.assertEqual(payload.creatine_g, 3.0)
        self.assertEqual(payload.glycine_g, 2.0)
        self.assertEqual(payload.taurine_g, 1.0)
        self.assertEqual(payload.l_leucine_g, 1.8)
        self.assertTrue(payload.has_added_free_form_aminos)

        # Spiking nitrogen delta:
        # Creatine (3.0 * 1.81 = 5.43) + Glycine (2.0 * 1.16 = 2.32) + Taurine (1.0 * 0.70 = 0.70) = 8.45g
        self.assertAlmostEqual(payload.spiking_nitrogen_delta_g, 8.45, delta=0.05)
        # True unspiked protein: 25g - 8.45g = 16.55g
        self.assertAlmostEqual(payload.true_protein_g, 16.55, delta=0.05)
        # Leucine to declared protein: 1.8 / 25 = 0.072 (7.2%, below natural intact whey 10.5%)
        self.assertAlmostEqual(payload.leucine_to_protein_ratio, 0.072, delta=0.005)

        # Integrated Amino Spiking Rules Engine Verification
        audit = payload.amino_spiking_audit
        self.assertTrue(bool(audit), "Integrated amino spiking audit should be populated!")
        self.assertEqual(audit["riskLevel"], "CONFIRMED_SPIKED", "Must classify multi-spiker as CONFIRMED_SPIKED")
        self.assertTrue(audit["aminoSpikeRisk"])
        self.assertIn("glycine", audit["detectedAgents"])
        self.assertIn("taurine", audit["detectedAgents"])
        self.assertIn("creatine monohydrate", audit["detectedAgents"])
        self.assertGreaterEqual(audit["trustDeduction"], 45)
        self.assertTrue(audit["quarantineRecommended"])

    def test_05_cross_dimensional_variant_unification_ocr_bridge(self):
        """
        Verify that a listing with '30 Servings' and no weight in title
        bridges to a 907g Master Variant via OCR serving_size_g = 30.2g (30 * 30.2g = 906g -> 907g bucket).
        """
        mock_master_catalog = [
            {
                "id": "var-master-907",
                "flavor": "chocolate",
                "weight_grams": 907,
                "sku_id": "OPTI-WHEY-907-CHO",
                "servings_count": 30,
                "products": {
                    "id": "prod-master-001",
                    "brand": "Optimum Nutrition",
                    "base_name": "Gold Standard 100% Whey",
                    "category_silo": "protein",
                    "protein_source": "Whey Blend",
                    "nutrition_serving_size_g": 30.2,
                    "nutrition_protein_per_serving_g": 24.0
                }
            }
        ]

        MasterCatalogMatcher.initialize_indexes(custom_catalog=mock_master_catalog)

        # Scraped listing has NO weight in title, only "30 Servings"
        scraped_title = "Optimum Nutrition Gold Standard Whey Double Rich Chocolate 30 Servings"
        matched = MasterCatalogMatcher.match_variant(
            scraped_title=scraped_title,
            scraped_weight_g=0,  # Missing in title!
            scraped_price_inr=3200.0,
            brand_hint="Optimum Nutrition"
        )

        self.assertIsNotNone(matched, "Should match via OCR serving size bridge!")
        self.assertEqual(matched["id"], "var-master-907")
        self.assertEqual(matched["weight_grams"], 907)

    def test_06_canopy_index_10k_benchmark(self):
        """
        Benchmark: 10,000 candidate lookup in canopy index executes in < 2.0 seconds.
        """
        mock_10k_catalog = []
        brands = ["Optimum Nutrition", "MuscleBlaze", "Nakpro", "As-It-Is", "Dymatize"]
        silos = ["protein", "creatine", "mass_gainer", "pre_workout"]
        flavors = ["chocolate", "vanilla", "strawberry", "mango", "unflavored"]
        weights = [250, 500, 1000, 2000, 4000]

        idx = 0
        for b in brands:
            for line_idx in range(40):  # 5 brands * 40 lines * 2 silos * 5 flavors * 5 weights = 10,000
                for s in ["protein", "creatine"]:
                    for f in flavors:
                        for w in weights:
                            idx += 1
                            mock_10k_catalog.append({
                                "id": f"var-{idx}",
                                "flavor": f,
                                "weight_grams": w,
                                "sku_id": f"SKU-{idx}",
                                "servings_count": int(w / 30),
                                "products": {
                                    "id": f"prod-{idx // 5}",
                                    "brand": b,
                                    "base_name": f"{b} Line {line_idx}",
                                    "category_silo": s,
                                    "protein_source": "Whey",
                                    "nutrition_serving_size_g": 30.0,
                                    "nutrition_protein_per_serving_g": 24.0
                                }
                            })

        self.assertEqual(len(mock_10k_catalog), 10000)

        # Build in-memory index
        t0 = time.time()
        MasterCatalogMatcher.initialize_indexes(custom_catalog=mock_10k_catalog)
        build_time = time.time() - t0
        print(f"\n[Benchmark] In-memory index build for 10,000 variants took {build_time:.3f}s")

        # Execute 500 matching lookups against the 10,000 catalog
        test_queries = [
            ("Optimum Nutrition Line 10 Chocolate 1000g", 1000, "Optimum Nutrition"),
            ("MuscleBlaze Line 5 Vanilla 2kg", 2000, "MuscleBlaze"),
            ("Nakpro Line 20 Unflavored 500g", 500, "Nakpro"),
            ("As-It-Is Line 1 Mango 1000g", 1000, "As-It-Is"),
            ("Dymatize Line 12 Strawberry 2000g", 2000, "Dymatize")
        ] * 100  # 500 total lookups

        t_start = time.time()
        matches_found = 0
        for title, w, brand in test_queries:
            res = MasterCatalogMatcher.match_variant(
                scraped_title=title,
                scraped_weight_g=w,
                scraped_price_inr=2500.0,
                brand_hint=brand
            )
            if res:
                matches_found += 1
        elapsed = time.time() - t_start

        print(f"[Benchmark] 500 lookups against 10,000-candidate catalog took {elapsed:.3f}s ({elapsed/500*1000:.2f}ms/lookup)")
        self.assertLess(elapsed, 2.0, f"Benchmark failed: 500 lookups took {elapsed:.2f}s (must be < 2.0s)")
        self.assertEqual(matches_found, 500, "All 500 queries should have matched successfully!")


if __name__ == '__main__':
    unittest.main()
