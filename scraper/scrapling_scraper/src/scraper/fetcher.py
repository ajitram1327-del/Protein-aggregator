import asyncio
import random
from typing import Dict, Optional, Tuple
from curl_cffi.requests import AsyncSession

class ResilientStealthFetcher:
    """
    Zero-fingerprint async transport matching Google Chrome 124 TLS/HTTP2 specs.
    Prevents Cloudflare / Akamai IP blocks without spinning up heavy headless browsers.
    Includes per-domain token bucket semaphores and HTTP conditional 304 handling.
    """
    def __init__(self):
        # Per-domain isolated semaphores (never bottleneck globally)
        self.domain_semaphores: Dict[str, asyncio.Semaphore] = {
            "amazon.in": asyncio.Semaphore(2),
            "flipkart.com": asyncio.Semaphore(3),
            "healthkart.com": asyncio.Semaphore(4),
            "nutrabay.com": asyncio.Semaphore(4),
            "default": asyncio.Semaphore(8),
        }
        self.domain_delays: Dict[str, Tuple[float, float]] = {
            "amazon.in": (1.8, 3.2),
            "flipkart.com": (1.2, 2.5),
            "healthkart.com": (0.8, 1.8),
            "nutrabay.com": (0.6, 1.5),
            "default": (0.1, 0.4),
        }
        self.session: Optional[AsyncSession] = None

    async def init_session(self):
        if not self.session:
            self.session = AsyncSession(
                impersonate="chrome124",
                timeout=20,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

    def _get_domain(self, url: str) -> str:
        for domain in self.domain_semaphores:
            if domain in url:
                return domain
        return "default"

    async def fetch(
        self, 
        url: str, 
        etag: Optional[str] = None, 
        last_modified: Optional[str] = None
    ) -> Tuple[int, str, Optional[str], Optional[str]]:
        """
        Executes a conditional HTTP request with random human jitter.
        Returns: (status_code, response_body, new_etag, new_last_modified)
        """
        await self.init_session()
        domain = self._get_domain(url)
        sem = self.domain_semaphores[domain]
        min_d, max_d = self.domain_delays.get(domain, (0.1, 0.4))

        async with sem:
            await asyncio.sleep(random.uniform(min_d, max_d))
            headers = {}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified

            try:
                assert self.session is not None
                res = await self.session.get(url, headers=headers)
                
                # 304 Not Modified -> Price & Stock are unchanged, 0 body transfer
                if res.status_code == 304:
                    return 304, "", etag, last_modified
                
                new_etag = res.headers.get("ETag")
                new_last_mod = res.headers.get("Last-Modified")
                return res.status_code, res.text, new_etag, new_last_mod

            except Exception as e:
                # Isolate connection timeout/failure so main loop never crashes
                return 599, str(e), None, None

    async def fetch_bytes(self, url: str) -> Optional[bytes]:
        await self.init_session()
        try:
            assert self.session is not None
            res = await self.session.get(url)
            if res.status_code == 200:
                return res.content
            return None
        except Exception:
            return None

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
