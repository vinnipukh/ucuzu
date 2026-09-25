#!/usr/bin/env python3
"""Exercise product search/detail and EpeyKatfg routes against the configured database."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from falcon.testing import TestClient
from inflation_dashboard.api.falcon_app import create_app

client = TestClient(create_app())

search = client.simulate_get("/api/products/search?q=ceket&limit=3")
print("Search status:", search.status)
search_payload = search.json
print("Search envelope keys:", list(search_payload.keys()))
print("Search count:", len(search_payload["data"]))
print("Search sample product:", search_payload["data"][0] if search_payload["data"] else None)

if search_payload["data"]:
    product = search_payload["data"][0]
    detail = client.simulate_get(
        f"/api/product?product_id={product['product_id']}&retailer={product['retailer']}"
    )
    print("\nProduct detail status:", detail.status)
    detail_payload = detail.json
    print("Product detail envelope keys:", list(detail_payload.keys()))
    print("Product detail summary:", detail_payload["data"]["summary"])
    print("Product detail history points:", len(detail_payload["data"]["history"]))

not_found = client.simulate_get("/api/product?product_id=NONEXISTENT_XYZ")
print("\n404 status:", not_found.status)
print("404 errors:", not_found.json["errors"])

invalid = client.simulate_get("/api/product")
print("\n400 status:", invalid.status)
print("400 errors:", invalid.json["errors"])

monthly = client.simulate_get("/api/epeykatfg/monthly-inflation")
print("\nMonthly status:", monthly.status)
print("Monthly rows:", len(monthly.json["data"]))
print("Monthly meta:", monthly.json["meta"])
