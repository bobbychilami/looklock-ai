#!/usr/bin/env python3
"""Fetch real product images for demo catalog via SerpApi (India-first)."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Ensure backend package importable when running from tools/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.catalog.product import ProductImage  # noqa: E402
from app.catalog.providers.serpapi_shopping import SerpApiShoppingProductProvider  # noqa: E402
from app.catalog.seed import CATALOGUE  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.catalog.providers.base import ProductQuery  # noqa: E402


def build_query(p) -> str:
    parts = [p.name, p.slot, p.category or "", p.subcategory or "", "classic", "india", "men"]
    # dedupe while preserving order
    seen = set()
    qparts = []
    for x in parts:
        x = str(x).lower().strip().replace("  ", " ")
        if x and x not in seen:
            seen.add(x)
            qparts.append(x)
    return " ".join(qparts)[:200]


async def main(download: bool = False) -> None:
    settings = Settings()
    provider = SerpApiShoppingProductProvider(settings=settings)
    if not provider.is_configured:
        print("SERPAPI_API_KEY not configured; skipping live fetch")
        return
    assets = BACKEND_ROOT / "app" / "catalog" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    results = []
    for p in CATALOGUE:
        q = ProductQuery(search_hint=build_query(p), limit=3)
        try:
            prods = await provider.search_products(q)
        except Exception as e:
            print(f"ERR {p.product_id}: {e}")
            continue
        found = []
        for sp in prods[:2]:
            img = getattr(sp, "image", None)
            if img is None:
                continue
            url = getattr(img, "url", None) or getattr(img, "local_path", None)
            if url and url.startswith("http"):
                found.append(url)
        results.append((p.product_id, found))
        print(f"{p.product_id}: {found}")
    if download:
        for pid, urls in results:
            for url in urls:
                try:
                    import httpx  # lazy import

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(url, follow_redirects=True)
                    if resp.status_code != 200:
                        continue
                    ct = resp.headers.get("content-type", "")
                    ext = ".jpg"
                    if "png" in ct:
                        ext = ".png"
                    elif "webp" in ct:
                        ext = ".webp"
                    h = hashlib.sha256(url.encode()).hexdigest()[:12]
                    fname = f"real_{pid}_{h}{ext}"
                    (assets / fname).write_bytes(resp.content)
                    print(f"saved {fname}")
                except Exception as e:
                    print(f"dl err {pid}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(download=args.download))
PY
