"""
test_golden_set.py - Golden Set Regression Test for ProteIndex Entity Normalization and Matching.
Ensures >=98% precision across complex real-world e-commerce titles, imperial weight conversions,
SEO noise, and promotional combo detection.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'scrapling_scraper'))
from src.pipeline.normalizer import CanonicalProductNormalizer, VariantNormalizer


GOLDEN_TEST_CASES = [
    # 1. NAKPRO IMPACT WHEY DIVERGENT TITLES (Must all resolve to Nakpro Impact Whey)
    {
        "title": "Nakpro Impact Whey Protein",
        "brand": "Nakpro",
        "expected_brand": "Nakpro",
        "expected_line": "Impact Whey",
        "expected_formulation": "Whey Blend",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "NAKPRO NUTRITION Impact Whey Protein Isolate & Concentrate Whey Protein - 1 Kg (Chocolate)",
        "brand": "Nakpro",
        "expected_brand": "Nakpro",
        "expected_line": "Impact Whey",
        "expected_formulation": "Whey Blend",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "NAKPRO Impact Whey Protein Powder (1kg, Vanilla)",
        "brand": "Nakpro",
        "expected_brand": "Nakpro",
        "expected_line": "Impact Whey",
        "expected_formulation": "Whey Blend",
        "expected_silo": "protein",
        "is_bundle": False
    },

    # 2. NAKPRO PERFORM WHEY
    {
        "title": "NAKPRO Perform Whey Protein Concentrate",
        "brand": "Nakpro",
        "expected_brand": "Nakpro",
        "expected_line": "Perform Whey Concentrate",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "NAKPRO NUTRITION Perform Whey Protein Concentrate (Chocolate, 2kg)",
        "brand": "Nakpro",
        "expected_brand": "Nakpro",
        "expected_line": "Perform Whey Concentrate",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "NAKPRO NUTRITION Perform Plus+ Whey Protein Concentrate",
        "brand": "Nakpro",
        "expected_brand": "Nakpro",
        "expected_line": "Perform Plus Whey Concentrate",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },

    # 3. OPTIMUM NUTRITION GOLD STANDARD & PRE-WORKOUT
    {
        "title": "Gold Standard 100% Whey Protein Powder",
        "brand": "Optimum Nutrition (ON)",
        "expected_brand": "Optimum Nutrition",
        "expected_line": "Gold Standard 100% Whey",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "Optimum Nutrition (ON) Gold Standard 100% Whey Protein Powder Double Rich Chocolate 2 kg (4.4 lb)",
        "brand": "Optimum Nutrition (ON)",
        "expected_brand": "Optimum Nutrition",
        "expected_line": "Gold Standard 100% Whey",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "Optimum Nutrition (ON) Gold Standard Pre-Workout 30 Servings (Green Apple)",
        "brand": "Optimum Nutrition (ON)",
        "expected_brand": "Optimum Nutrition",
        "expected_line": "Gold Standard Pre-Workout",
        "expected_formulation": "Pre-Workout",
        "expected_silo": "pre_workout",
        "is_bundle": False
    },
    {
        "title": "Optimum Nutrition (ON) Micronized Creatine Powder 250g",
        "brand": "Optimum Nutrition (ON)",
        "expected_brand": "Optimum Nutrition",
        "expected_line": "Micronized Creatine Powder",
        "expected_formulation": "Creatine Monohydrate",
        "expected_silo": "creatine",
        "is_bundle": False
    },

    # 4. MUSCLEBLAZE BIOZYME PERFORMANCE WHEY
    {
        "title": "MuscleBlaze Biozyme Performance Whey",
        "brand": "MuscleBlaze",
        "expected_brand": "MuscleBlaze",
        "expected_line": "Biozyme Performance Whey",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "Muscleblaze Biozyme Performance Whey Protein With Us Patent Rich Chocolate 2kg",
        "brand": "MuscleBlaze",
        "expected_brand": "MuscleBlaze",
        "expected_line": "Biozyme Performance Whey",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },

    # 5. ISOPURE ZERO CARB
    {
        "title": "Isopure Zero Carb Protein 500g / 1.1lb (Unflavoured)",
        "brand": "Isopure",
        "expected_brand": "Isopure",
        "expected_line": "Zero Carb Whey Isolate",
        "expected_formulation": "Whey Isolate",
        "expected_silo": "protein",
        "is_bundle": False
    },
    {
        "title": "Isopure Zero Carb Whey Protein Isolate Powder 2 kg (Unflavoured)",
        "brand": "Isopure",
        "expected_brand": "Isopure",
        "expected_line": "Zero Carb Whey Isolate",
        "expected_formulation": "Whey Isolate",
        "expected_silo": "protein",
        "is_bundle": False
    },

    # 6. AS-IT-IS ATOM WHEY
    {
        "title": "AS-IT-IS ATOM Performance Whey 1Kg",
        "brand": "AS-IT-IS Nutrition",
        "expected_brand": "AS-IT-IS",
        "expected_line": "ATOM Performance Whey",
        "expected_formulation": "Whey Concentrate",
        "expected_silo": "protein",
        "is_bundle": False
    },

    # 7. PROMOTIONAL COMBOS & BUNDLES (Must be flagged as is_bundle = True)
    {
        "title": "FREE Creatine 100g with Gold Standard 100% Whey Double Rich Chocolate",
        "brand": "Optimum Nutrition (ON)",
        "is_bundle": True
    },
    {
        "title": "Nakpro Gold 1kg + Benchmark Creatine 100g with Free Shaker",
        "brand": "Nakpro",
        "is_bundle": True
    },
    {
        "title": "MuscleBlaze Biozyme Whey 2kg + Free Sipper Bottle",
        "brand": "MuscleBlaze",
        "is_bundle": True
    },
    {
        "title": "Gold Standard 100% Whey 2 Lbs Double Rich Chocolate + Creatine 100 g",
        "brand": "Optimum Nutrition (ON)",
        "is_bundle": True
    },
    {
        "title": "Buy 1 Get 1 Free Nakpro Whey Protein Powder",
        "brand": "Nakpro",
        "is_bundle": True
    },
    {
        "title": "Whey Protein Powder Pack of 2 (1kg each)",
        "brand": "AS-IT-IS",
        "is_bundle": True
    }
]


def test_golden_set_precision():
    passed = 0
    failed = 0
    failures = []

    for idx, case in enumerate(GOLDEN_TEST_CASES):
        title = case["title"]
        brand = case.get("brand")
        info = CanonicalProductNormalizer.normalize_product(title, brand)

        if case.get("is_bundle"):
            if not info.is_bundle:
                failed += 1
                failures.append(f"Case {idx + 1}: '{title}' should be flagged as BUNDLE, but was not.")
            else:
                passed += 1
            continue

        # Regular single SKU tests
        if info.is_bundle:
            failed += 1
            failures.append(f"Case {idx + 1}: '{title}' was incorrectly flagged as BUNDLE ({info.bundle_reason}).")
            continue

        errors = []
        if info.canonical_brand != case["expected_brand"]:
            errors.append(f"brand: got '{info.canonical_brand}', expected '{case['expected_brand']}'")
        if info.canonical_line != case["expected_line"]:
            errors.append(f"line: got '{info.canonical_line}', expected '{case['expected_line']}'")
        if info.category_silo != case["expected_silo"]:
            errors.append(f"silo: got '{info.category_silo}', expected '{case['expected_silo']}'")

        if errors:
            failed += 1
            failures.append(f"Case {idx + 1} '{title}': " + ", ".join(errors))
        else:
            passed += 1

    total = len(GOLDEN_TEST_CASES)
    precision = (passed / total) * 100.0

    print(f"\n[GOLDEN SET] {passed}/{total} Passed ({precision:.1f}% Precision)")
    if failures:
        print("\nFailures:")
        for f in failures:
            print("  - " + f)

    assert precision >= 98.0, f"Golden set precision {precision:.1f}% is below required 98.0% threshold!"


def test_weight_normalization_golden():
    # 2.2 lbs -> 1000g
    assert VariantNormalizer.parse_weight("2.2 lbs") == 1000
    # 4.4 lbs -> 2000g
    assert VariantNormalizer.parse_weight("4.4 lbs") == 2000
    # 5 lbs -> 2268g
    assert VariantNormalizer.parse_weight("5 lbs") == 2268
    # 1kg -> 1000g
    assert VariantNormalizer.parse_weight("1kg") == 1000
    # Nutrient claim stripped: 24g Protein per scoop in a 1kg tub -> 1000g
    assert VariantNormalizer.parse_weight("24g Protein Per Scoop, 1kg Tub") == 1000


if __name__ == '__main__':
    test_golden_set_precision()
    test_weight_normalization_golden()
    print("All Golden Set tests passed successfully!")
