"""
ProteIndex Scraper Engine — Module 2: Multi-Platform D2C Adaptor Cascade
Provides unified extraction across:
1. Shopify Fast-Track (/products.json?limit=250)
2. WooCommerce Store API (/wp-json/wc/store/v1/products, e.g. Avvatar)
3. Next.js Pre-rendered Hydration State (__NEXT_DATA__)
4. HealthKart D2C API Gateway (e.g. MuscleBlaze, HK Vitals)
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

from src.scraper.sanitizer import is_promotional_combo, extract_normalized_grams

logger = logging.getLogger("D2CAdapters")


class D2CAdapterRegistry:
    """
    Auto-detects the underlying e-commerce architecture of any D2C storefront
    and delegates to the optimal parsing strategy without throwing hard exceptions.
    """

    @staticmethod
    def parse_shopify_payload(data: Dict[str, Any], brand_name: str) -> List[Dict[str, Any]]:
        """
        Extracts clean, normalized single-SKU records from Shopify /products.json.
        Filters promotional combos, unpacks variants, and normalizes weights.
        """
        clean_products = []
        for prod in data.get("products", []):
            title = prod.get("title", "")
            handle = prod.get("handle", "")
            prod_type = prod.get("product_type", "")
            tags = prod.get("tags", [])
            body_html = prod.get("body_html", "") or ""
            images = prod.get("images", [])
            img_url = images[0].get("src") if images else None

            # Stage 1: Combo and accessory filtering
            is_combo, reason = is_promotional_combo(title)
            if is_combo:
                logger.debug(f"[Shopify] Quarantining bundle: '{title}' ({reason})")
                continue

            # Skip non-supplement items
            tag_str = " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            if any(k in tag_str for k in ["shaker", "apparel", "tshirt", "bottle", "bag"]):
                continue

            for v in prod.get("variants", []):
                v_title = v.get("title", "")
                full_name = f"{title} {v_title}".strip()
                v_price = float(v.get("price", 0.0))
                v_available = v.get("available", True)
                v_sku = str(v.get("sku") or v.get("id"))

                # Extract normalized weight
                weight_g = extract_normalized_grams(full_name, raw_weight_field=v.get("weight_unit"))
                if not weight_g and v.get("grams"):
                    try:
                        g_val = int(v["grams"])
                        if 50 <= g_val <= 25000:
                            weight_g = g_val
                    except (ValueError, TypeError):
                        pass

                if not weight_g:
                    # Fallback to description body
                    weight_g = extract_normalized_grams(body_html)

                if not weight_g:
                    continue

                # Flavor extraction heuristics
                flavor = "Unflavored"
                flavor_candidates = [
                    v.get("option1"), v.get("option2"), v.get("option3")
                ]
                for fc in flavor_candidates:
                    if fc and not re.search(r'\b(?:\d+\s*(?:kg|g|lbs?)|default\s*title)\b', str(fc), re.I):
                        flavor = str(fc).strip()
                        break

                clean_products.append({
                    "brand": brand_name,
                    "title": title,
                    "full_title": full_name,
                    "flavor": flavor,
                    "weight_grams": weight_g,
                    "price_inr": v_price,
                    "in_stock": v_available,
                    "sku_id": v_sku,
                    "url_handle": handle,
                    "image_url": img_url,
                    "platform": "Shopify"
                })

        return clean_products

    @staticmethod
    def parse_woocommerce_payload(data: List[Dict[str, Any]], brand_name: str) -> List[Dict[str, Any]]:
        """
        Parses standard WooCommerce Store API /wp-json/wc/store/v1/products response
        (Used by Avvatar, Divine Nutrition, etc.)
        """
        clean_products = []
        for item in data:
            title = item.get("name", "")
            permalink = item.get("permalink", "")
            images = item.get("images", [])
            img_url = images[0].get("src") if images else None

            is_combo, reason = is_promotional_combo(title)
            if is_combo:
                continue

            # Pricing: WooCommerce Store API returns minor units (paise)
            raw_prices = item.get("prices", {})
            raw_price = raw_prices.get("price", "0")
            try:
                price_inr = float(raw_price) / 100.0 if len(str(raw_price)) > 4 else float(raw_price)
            except (ValueError, TypeError):
                price_inr = 0.0

            weight_g = extract_normalized_grams(title, description=item.get("description", ""))
            if not weight_g:
                continue

            # Variation handling
            variations = item.get("variations", [])
            if variations:
                for var in variations:
                    v_attributes = var.get("attributes", [])
                    var_flavor = "Unflavored"
                    for attr in v_attributes:
                        if "flavor" in attr.get("name", "").lower():
                            var_flavor = attr.get("value", "Unflavored")

                    var_price_raw = var.get("price", raw_price)
                    try:
                        v_price = float(var_price_raw) / 100.0 if len(str(var_price_raw)) > 4 else float(var_price_raw)
                    except (ValueError, TypeError):
                        v_price = price_inr

                    clean_products.append({
                        "brand": brand_name,
                        "title": title,
                        "full_title": f"{title} - {var_flavor}",
                        "flavor": var_flavor,
                        "weight_grams": weight_g,
                        "price_inr": v_price,
                        "in_stock": var.get("is_in_stock", True),
                        "sku_id": str(var.get("id")),
                        "url_handle": permalink,
                        "image_url": img_url,
                        "platform": "WooCommerce"
                    })
            else:
                clean_products.append({
                    "brand": brand_name,
                    "title": title,
                    "full_title": title,
                    "flavor": "Unflavored",
                    "weight_grams": weight_g,
                    "price_inr": price_inr,
                    "in_stock": item.get("is_in_stock", True),
                    "sku_id": str(item.get("id")),
                    "url_handle": permalink,
                    "image_url": img_url,
                    "platform": "WooCommerce"
                })

        return clean_products

    @staticmethod
    def parse_nextjs_hydration(html_text: str, brand_name: str) -> List[Dict[str, Any]]:
        """
        Extracts catalog entities from Next.js pre-rendered hydration payloads
        <script id="__NEXT_DATA__" type="application/json">...</script>
        """
        clean_products = []
        soup = BeautifulSoup(html_text, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag or not script_tag.string:
            return clean_products

        try:
            next_data = json.loads(script_tag.string)
            page_props = next_data.get("props", {}).get("pageProps", {})
            catalog_list = (
                page_props.get("products") or
                page_props.get("initialState", {}).get("catalog", {}).get("items") or
                page_props.get("dehydratedState", {}).get("queries", [{}])[0].get("state", {}).get("data", {}).get("products") or
                []
            )

            for item in catalog_list:
                name = item.get("name") or item.get("title") or ""
                if not name:
                    continue

                is_combo, _ = is_promotional_combo(name)
                if is_combo:
                    continue

                price = float(item.get("sellingPrice") or item.get("price") or item.get("offerPrice") or 0.0)
                weight_g = extract_normalized_grams(name)
                if not weight_g:
                    continue

                flavor = item.get("flavor") or "Unflavored"
                sku = str(item.get("sku") or item.get("id") or item.get("productId"))

                clean_products.append({
                    "brand": brand_name,
                    "title": name,
                    "full_title": f"{name} {flavor}".strip(),
                    "flavor": flavor,
                    "weight_grams": weight_g,
                    "price_inr": price,
                    "in_stock": item.get("inStock", True),
                    "sku_id": sku,
                    "url_handle": item.get("slug") or item.get("url") or "",
                    "image_url": item.get("imageUrl") or item.get("image"),
                    "platform": "NextJS"
                })
        except Exception as e:
            logger.warning(f"Error parsing Next.js hydration state: {e}")

        return clean_products

    @staticmethod
    def parse_healthkart_gateway(data: Dict[str, Any], brand_name: str = "MuscleBlaze") -> List[Dict[str, Any]]:
        """
        Parses HealthKart catalog payloads (Used for MuscleBlaze, TrueBasics, HK Vitals).
        """
        clean_products = []
        results = data.get("results", []) or data.get("data", {}).get("products", []) or []

        for p in results:
            name = p.get("name") or p.get("title") or ""
            is_combo, _ = is_promotional_combo(name)
            if is_combo:
                continue

            variants = p.get("variants") or p.get("childSkus") or [p]
            for v in variants:
                var_name = v.get("name") or name
                price = float(v.get("offerPrice") or v.get("finalPrice") or v.get("price") or 0.0)
                weight_g = extract_normalized_grams(var_name)
                if not weight_g:
                    continue

                flavor = v.get("flavor") or "Unflavored"
                clean_products.append({
                    "brand": brand_name,
                    "title": name,
                    "full_title": var_name,
                    "flavor": flavor,
                    "weight_grams": weight_g,
                    "price_inr": price,
                    "in_stock": v.get("inStock", True),
                    "sku_id": str(v.get("id") or v.get("skuId") or ""),
                    "url_handle": v.get("url") or "",
                    "image_url": v.get("imageUrl") or "",
                    "platform": "HealthKart"
                })

        return clean_products
