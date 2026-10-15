"""
ProteIndex Scraper Engine — Module 3: Marketplace Variant & Twister Resolver
Provides:
- MarketplaceRateLimiter: Per-domain token bucket rate limiter with randomized jitter (1.8s - 3.2s)
- AmazonTwisterParser: Unpacks child ASINs and dimension matrices from product pages
- FlipkartSwatchParser: Unpacks child FSNs from swatch selectors
- poll_canonical_marketplace_sku: Direct canonical item pricing updater
"""

import asyncio
import json
import logging
import random
import re
import time
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

from src.scraper.sanitizer import extract_normalized_grams, is_promotional_combo

logger = logging.getLogger("MarketplaceResolver")


class MarketplaceRateLimiter:
    """
    Token bucket rate limiter with randomized jitter between requests
    to avoid triggering commercial anti-bot tripwires.
    """
    def __init__(self, min_delay_sec: float = 1.8, max_delay_sec: float = 3.2):
        self.min_delay = min_delay_sec
        self.max_delay = max_delay_sec
        self._last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def throttle(self, domain: str):
        async with self._lock:
            now = time.time()
            last = self._last_request_time.get(domain, 0.0)
            elapsed = now - last
            required_wait = random.uniform(self.min_delay, self.max_delay)

            if elapsed < required_wait:
                wait_time = required_wait - elapsed
                await asyncio.sleep(wait_time)

            self._last_request_time[domain] = time.time()


class AmazonTwisterParser:
    """
    Unpacks Amazon India twister dimension variations (Flavor, Size)
    and maps child ASINs to real metric weights.
    """

    @staticmethod
    def extract_twister_variants(html: str, parent_asin: str) -> List[Dict[str, Any]]:
        extracted = []
        soup = BeautifulSoup(html, "html.parser")

        # 1. Look for dimensionValuesDisplayData or variationValues JSON script block
        scripts = soup.find_all("script", type="text/javascript")
        twister_data = None
        for s in scripts:
            if s.string and "dimensionValuesDisplayData" in s.string:
                match = re.search(r'data\["dimensionValuesDisplayData"\]\s*=\s*({.*?});', s.string)
                if match:
                    try:
                        twister_data = json.loads(match.group(1))
                        break
                    except Exception:
                        pass

        # 2. Extract ASIN to dimension mappings
        if twister_data:
            for child_asin, dimensions in twister_data.items():
                dim_str = " ".join([str(d) for d in dimensions if d])
                weight_g = extract_normalized_grams(dim_str)
                flavor = dimensions[0] if len(dimensions) > 0 else "Unflavored"

                extracted.append({
                    "asin": child_asin,
                    "flavor": str(flavor),
                    "weight_grams": weight_g,
                    "dimensions": dimensions,
                    "source": "Amazon India"
                })

        return extracted


class FlipkartSwatchParser:
    """
    Extracts variants from Flipkart swatch pills (Flavor, Size) and associated FSNs.
    """

    @staticmethod
    def extract_swatches(html: str) -> List[Dict[str, Any]]:
        extracted = []
        soup = BeautifulSoup(html, "html.parser")

        # Swatch container selector
        swatch_items = soup.select("li._3V2wfe, div._2C41 Cricket")
        for item in swatch_items:
            fsn_link = item.find("a", href=True)
            if not fsn_link:
                continue

            href = fsn_link["href"]
            fsn_match = re.search(r'pid=([A-Z0-9]+)', href)
            fsn = fsn_match.group(1) if fsn_match else None
            text = item.get_text(strip=True)

            if fsn:
                extracted.append({
                    "fsn": fsn,
                    "title": text,
                    "weight_grams": extract_normalized_grams(text),
                    "url": f"https://www.flipkart.com{href}" if href.startswith("/") else href,
                    "source": "Flipkart"
                })

        return extracted


async def poll_canonical_marketplace_sku(
    fetcher: Any,
    rate_limiter: MarketplaceRateLimiter,
    platform: str,
    sku_identifier: str,
    product_url: str
) -> Optional[Dict[str, Any]]:
    """
    Directly polls a canonical Marketplace listing (Amazon ASIN or Flipkart FSN)
    with rate limiting and returns the live price and in_stock status.
    """
    domain = "amazon.in" if "amazon" in platform.lower() else "flipkart.com"
    await rate_limiter.throttle(domain)

    try:
        html = await fetcher.fetch_html(product_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        if "amazon" in platform.lower():
            # Price extraction
            price_elem = soup.select_one("span.a-price-whole, span#priceblock_ourprice, span#priceblock_dealprice")
            stock_elem = soup.select_one("div#availability span")

            if price_elem:
                raw_price = re.sub(r'[^\d.]', '', price_elem.get_text())
                price = float(raw_price) if raw_price else 0.0
                in_stock = True
                if stock_elem and any(w in stock_elem.get_text().lower() for w in ["unavailable", "out of stock"]):
                    in_stock = False

                return {
                    "platform": "Amazon",
                    "sku": sku_identifier,
                    "price_inr": price,
                    "in_stock": in_stock,
                    "url": product_url
                }

        elif "flipkart" in platform.lower():
            price_elem = soup.select_one("div._30jeq3, div.Nx9bqj")
            stock_elem = soup.select_one("div._16FRp0, button._2KpZ6l")

            if price_elem:
                raw_price = re.sub(r'[^\d.]', '', price_elem.get_text())
                price = float(raw_price) if raw_price else 0.0
                in_stock = "buy now" in html.lower() or "add to cart" in html.lower()

                return {
                    "platform": "Flipkart",
                    "sku": sku_identifier,
                    "price_inr": price,
                    "in_stock": in_stock,
                    "url": product_url
                }

    except Exception as e:
        logger.warning(f"Error polling canonical SKU {sku_identifier} on {platform}: {e}")

    return None
