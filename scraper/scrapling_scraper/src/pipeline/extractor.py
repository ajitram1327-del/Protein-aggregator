import re
import json
from typing import Optional, Dict, Any, Tuple
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.pipeline.normalizer import VariantNormalizer

class MultiLevelExtractor:
    """
    Cascading 4-level extractor that resolves missing weight, flavor, and specs
    when the product title is vague or uninformative.
    Level 1: Title Regex (kg, g, lbs, multipacks)
    Level 2: JSON-LD / Schema.org Microdata (<script type="application/ld+json">)
    Level 3: Technical Specification Tables (Amazon / Flipkart / HealthKart tables)
    Level 4: Active Variant Selector Pills / Chips
    """

    @classmethod
    def resolve_specifications(
        cls, 
        raw_title: str, 
        html_body: str
    ) -> Tuple[Optional[int], str, str]:
        """
        Returns: (weight_grams, canonical_flavor, extraction_method)
        """
        # LEVEL 1: TITLE REGEX
        weight_g = VariantNormalizer.parse_weight(raw_title)
        flavor = VariantNormalizer.parse_flavor(raw_title)
        if weight_g and weight_g != 1000 and flavor != "unflavored":
            return weight_g, flavor, "title_regex"

        # LEVEL 2: JSON-LD / SCHEMA.ORG MICRODATA
        json_ld_data = cls._parse_json_ld(html_body)
        if json_ld_data:
            if not weight_g or weight_g == 1000:
                ld_weight = cls._extract_weight_from_json_ld(json_ld_data)
                if ld_weight:
                    weight_g = ld_weight
            if flavor == "unflavored":
                ld_flavor = VariantNormalizer.parse_flavor(json_ld_data.get("description", "") + " " + json_ld_data.get("name", ""))
                if ld_flavor != "unflavored":
                    flavor = ld_flavor

        if weight_g and weight_g != 1000 and flavor != "unflavored":
            return weight_g, flavor, "json_ld_microdata"

        # LEVEL 3: TECHNICAL SPECIFICATION TABLES
        if not weight_g or weight_g == 1000:
            specs_weight = cls._extract_from_tech_specs_table(html_body)
            if specs_weight:
                weight_g = specs_weight

        if weight_g and weight_g != 1000 and flavor != "unflavored":
            return weight_g, flavor, "specs_table"

        # LEVEL 4: ACTIVE VARIANT PILLS / BUTTON CHIPS
        if not weight_g or weight_g == 1000 or flavor == "unflavored":
            p_weight, p_flavor = cls._extract_from_variant_pills(html_body)
            if p_weight:
                weight_g = p_weight
            if flavor == "unflavored" and p_flavor != "unflavored":
                flavor = p_flavor

        method = "multilevel_fallback" if (weight_g and weight_g > 0) else "failed"
        return weight_g, flavor, method

    @classmethod
    def _parse_json_ld(cls, html_body: str) -> Optional[Dict[str, Any]]:
        matches = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html_body, re.DOTALL | re.IGNORECASE)
        for blob in matches:
            try:
                data = json.loads(blob.strip())
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Product":
                            return item
                elif isinstance(data, dict) and data.get("@type") == "Product":
                    return data
            except Exception:
                continue
        return None

    @classmethod
    def _extract_weight_from_json_ld(cls, data: Dict[str, Any]) -> Optional[int]:
        weight_block = data.get("weight")
        if isinstance(weight_block, dict):
            val = weight_block.get("value")
            unit = str(weight_block.get("unitCode", "")).upper()
            if val and unit in ["KGM", "KG"]: return int(float(val) * 1000)
            if val and unit in ["GRM", "G"]: return int(float(val))
            if val and unit in ["LBR", "LB"]: return int(float(val) * 453.592)
        desc = data.get("description", "")
        if desc:
            return VariantNormalizer.parse_weight(desc)
        return None

    @classmethod
    def _extract_from_tech_specs_table(cls, html_body: str) -> Optional[int]:
        patterns = [
            r'(?:item weight|net weight|net quantity|package weight)[\s\S]{1,150}?<td>([\d\.]+\s*(?:kg|g|lbs|gm))',
            r'<th[^>]*>(?:weight|net quantity)</th>[\s\S]{1,100}?>(?:<span[^>]*>)?([\d\.]+\s*(?:kg|g|lbs|gm))',
            r'"net_weight":\s*"([\d\.]+\s*(?:kg|g|lbs|gm))"',
        ]
        for pat in patterns:
            match = re.search(pat, html_body, re.IGNORECASE)
            if match:
                w = VariantNormalizer.parse_weight(match.group(1))
                if w and w > 0:
                    return w
        return None

    @classmethod
    def _extract_from_variant_pills(cls, html_body: str) -> Tuple[Optional[int], str]:
        active_pill_pattern = r'class=[\'"][^\'"]*(?:swatch-selected|active-pill|selected-variant)[^\'"]*[\'"][^>]*>([\s\S]{1,200}?)<'
        matches = re.findall(active_pill_pattern, html_body, re.IGNORECASE)
        w, f = None, "unflavored"
        for m in matches:
            if not w:
                extracted = VariantNormalizer.parse_weight(m)
                if extracted and extracted != 1000:
                    w = extracted
            if f == "unflavored":
                fl = VariantNormalizer.parse_flavor(m)
                if fl != "unflavored":
                    f = fl
        return w, f
