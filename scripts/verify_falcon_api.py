#!/usr/bin/env python
"""In-process Falcon API verification: import boundaries, routes and envelopes.

Run from the repository root with:
    uv run python scripts/verify_falcon_api.py

With a built database every data endpoint is exercised; without one, the data
endpoints must return 503 ``database_unavailable``.

The script uses Falcon's in-process TestClient only; it does not bind ports or
start a long-running server.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import quote
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ENVELOPE_KEYS = {"data", "meta", "errors"}
DEFAULT_RETAILER = "Markets / Gurmar"
FORBIDDEN_API_IMPORTS = ("streamlit", "streamlit_app", "plotly")
FORBIDDEN_CORE_IMPORTS = ("falcon", "streamlit", "plotly")
FORBIDDEN_CACHE_IMPORTS = ("redis", "sqlalchemy", "django", "peewee", "sqlite3")


def _is_forbidden_import(source: str, module: str) -> bool:
    """True if ``source`` has a top-level ``import module`` or ``from module`` line."""
    return bool(re.search(rf"^\s*(import\s+{re.escape(module)}\b|from\s+{re.escape(module)}\b)", source, re.MULTILINE))


def _iter_python_files(*relative_paths: str) -> list[Path]:
    """Collect ``.py`` files from the given repository-relative files or directories."""
    files: list[Path] = []
    for relative_path in relative_paths:
        path = REPO_ROOT / relative_path
        if path.is_file():
            files.append(path)
        else:
            files.extend(sorted(path.glob("*.py")))
    return files


def _assert_import_boundaries() -> None:
    """Check the layer import rules.

    ``api/`` must not import UI or database/cache clients (including ``sqlite3``);
    domain, application and adapters must not import Falcon; ``HealthResource`` must
    not load inventory or history.
    """
    api_files = _iter_python_files("inflation_dashboard/api")
    core_files = _iter_python_files(
        "inflation_dashboard/domain",
        "inflation_dashboard/application",
        "inflation_dashboard/adapters",
    )

    for path in api_files:
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_API_IMPORTS:
            assert not _is_forbidden_import(source, module), f"{path} imports forbidden API module {module}"
        for module in FORBIDDEN_CACHE_IMPORTS:
            assert not _is_forbidden_import(source, module), f"{path} imports forbidden cache/database module {module}"

    for path in core_files:
        source = path.read_text(encoding="utf-8")
        for module in FORBIDDEN_CORE_IMPORTS:
            assert not _is_forbidden_import(source, module), f"{path} imports forbidden core module {module}"

    resources_source = (REPO_ROOT / "inflation_dashboard/api/resources.py").read_text(encoding="utf-8")
    health_match = re.search(r"class HealthResource:.*?(?=\nclass InventoryResource:)", resources_source, re.DOTALL)
    assert health_match, "HealthResource body not found"
    health_body = health_match.group(0)
    for token in ("get_inventory", "load_filtered_history"):
        assert token not in health_body, f"HealthResource must not reference {token}"

    print("PASS boundary checks: imports, stdlib-only cache boundary, lightweight health resource")


def _assert_source_contracts() -> None:
    """Check that all fourteen routes are registered and the stable response keys appear in resources.py."""
    app_source = (REPO_ROOT / "inflation_dashboard/api/falcon_app.py").read_text(encoding="utf-8")
    for path in (
        "/api/health",
        "/api/inventory",
        "/api/history",
        "/api/retailer-averages",
        "/api/movers",
        "/api/coverage",
        "/api/products",
        "/api/products/search",
        "/api/epeykatfg/monthly-inflation",
        "/api/catalog/groups",
        "/api/catalog/search",
        "/api/catalog/item",
        "/api/catalog/deals",
        "/api/product",
    ):
        assert path in app_source, f"app factory missing route {path}"

    resources_source = (REPO_ROOT / "inflation_dashboard/api/resources.py").read_text(encoding="utf-8")
    for token in (
        '"retailers"',
        '"min_date"',
        '"max_date"',
        '"history"',
        '"summary"',
        '"records"',
        '"biggest_drops"',
        '"biggest_gains"',
        '"coverage_over_time"',
        '"category_coverage"',
        '"skipped_files"',
        '"skipped_file_count"',
    ):
        assert token in resources_source, f"resources.py missing response contract token {token}"

    print("PASS source contracts: endpoint routes and stable response keys")


def _load_client() -> Any:
    """Return a Falcon ``TestClient`` for ``create_app()``, with a hint if Falcon is not installed."""
    try:
        from falcon.testing import TestClient
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Falcon is missing. Install project dependency metadata with the user's uv workflow "
            "(for example: uv sync or uv pip install -r requirements.txt), then rerun "
            "python scripts/verify_falcon_api.py."
        ) from exc

    from inflation_dashboard.api.falcon_app import create_app

    return TestClient(create_app())


def _assert_json_native(value: Any, path: str = "$") -> None:
    """Recursively assert that a payload holds only JSON-native values (no NaN/Infinity, pandas or numpy)."""
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        assert math.isfinite(value), f"{path} contains NaN or Infinity"
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_json_native(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str), f"{path} contains non-string key {key!r}"
            _assert_json_native(item, f"{path}.{key}")
        return
    module = type(value).__module__
    assert not module.startswith(("pandas", "numpy")), f"{path} leaked {module}.{type(value).__name__}"
    raise AssertionError(f"{path} contains non-JSON-native {type(value).__name__}")


def _assert_envelope(payload: dict[str, Any], label: str) -> None:
    """Assert exactly the ``{data, meta, errors}`` keys and JSON-native content."""
    assert set(payload.keys()) == ENVELOPE_KEYS, f"{label} envelope keys were {set(payload.keys())}"
    json.dumps(payload, allow_nan=False)
    _assert_json_native(payload, label)
    assert isinstance(payload["errors"], list), f"{label} errors must be a list"


def _get(client: Any, path: str, expected_status: str = "200 OK") -> dict[str, Any]:
    """GET ``path``, assert the status and envelope, and return the parsed payload."""
    result = client.simulate_get(path)
    assert result.status == expected_status, f"{path} returned {result.status}: {result.text}"
    payload = result.json
    assert isinstance(payload, dict), f"{path} did not return a JSON object"
    _assert_envelope(payload, path)
    return payload


def _assert_endpoint_shapes(responses: dict[str, dict[str, Any]]) -> None:
    """Assert the key data/meta fields of each filter endpoint's response."""
    inventory = responses["inventory"]
    assert {"retailers", "min_date", "max_date"}.issubset(inventory["data"]), "inventory data keys missing"
    assert "file_count" in inventory["meta"] and "inventory_file_count" in inventory["meta"], "inventory counts missing"

    history = responses["history"]
    assert isinstance(history["data"].get("history"), list), "history data.history must be a list"

    averages = responses["retailer_averages"]
    assert isinstance(averages["data"].get("records"), list), "retailer averages data.records must be a list"

    movers = responses["movers"]
    assert isinstance(movers["data"].get("biggest_drops"), list), "movers biggest_drops missing"
    assert isinstance(movers["data"].get("biggest_gains"), list), "movers biggest_gains missing"

    coverage = responses["coverage"]
    assert {"summary", "coverage_over_time", "category_coverage", "skipped_files"}.issubset(coverage["data"]), (
        "coverage data keys missing"
    )
    assert "skipped_file_count" in coverage["meta"], "coverage skipped_file_count missing"


def run_endpoint_smoke() -> None:
    """Exercise the endpoints through the TestClient.

    Without a database: data routes must return 503 ``database_unavailable`` and the
    monthly inflation route must still work. With one: every data endpoint, product
    search, monthly inflation, an unknown product and an unknown retailer (400).
    """
    client = _load_client()
    health = _get(client, "/api/health")
    assert health["data"].get("status") == "ok"

    if health["data"].get("database") != "available":
        for path in (
            "/api/inventory",
            "/api/history?max_files=1",
            "/api/products?retailer=Markets%20%2F%20Gurmar",
            "/api/products/search?q=ceket&limit=3",
            "/api/product?product_id=__missing__",
            "/api/catalog/search?q=s%C3%BCt",
        ):
            unavailable = _get(client, path, expected_status="503 Service Unavailable")
            assert unavailable["data"] is None, f"{path} 503 data must be null"
            assert unavailable["errors"][0].get("code") == "database_unavailable", f"{path} 503 code mismatch"
        monthly = _get(client, "/api/epeykatfg/monthly-inflation")
        assert isinstance(monthly["data"], list), "monthly inflation data must be an array"
        print("PASS endpoint smoke: no database; data routes return 503 database_unavailable, monthly artifact served")
        return

    inventory = _get(client, "/api/inventory")
    retailers = [str(value) for value in inventory["data"].get("retailers", []) if value]
    if not retailers:
        search = _get(client, "/api/products/search?q=ceket&limit=3")
        assert isinstance(search["data"], list), "product search data must be an array"
        monthly = _get(client, "/api/epeykatfg/monthly-inflation")
        assert isinstance(monthly["data"], list), "monthly inflation data must be an array"
        missing = _get(client, "/api/product?product_id=__missing__", expected_status="404 Not Found")
        assert missing["errors"], "missing product response must include an error"
        print("PASS endpoint smoke: empty deployment envelopes, product search, monthly artifact, product 404")
        return

    retailer = DEFAULT_RETAILER if DEFAULT_RETAILER in retailers else retailers[0]
    encoded_retailer = quote(retailer, safe="")
    responses = {
        "health": health,
        "inventory": inventory,
        "history": _get(client, f"/api/history?retailer={encoded_retailer}&max_files=1"),
        "retailer_averages": _get(
            client,
            f"/api/retailer-averages?retailer={encoded_retailer}&max_files=1&aggregation=Average",
        ),
        "movers": _get(client, f"/api/movers?retailer={encoded_retailer}&max_files=1&limit=5"),
        "coverage": _get(client, f"/api/coverage?retailer={encoded_retailer}&max_files=1&category_limit=20"),
    }
    _assert_endpoint_shapes(responses)

    products = _get(client, f"/api/products?retailer={encoded_retailer}")
    assert isinstance(products["data"], list), "product list data must be an array"
    assert all({"retailer", "products"} <= set(group) for group in products["data"]), "product list group keys missing"

    search = _get(client, f"/api/products/search?q=ceket&retailer={encoded_retailer}&limit=3")
    assert isinstance(search["data"], list), "product search data must be an array"
    monthly = _get(client, "/api/epeykatfg/monthly-inflation")
    assert isinstance(monthly["data"], list), "monthly inflation data must be an array"

    product_empty = _get(
        client,
        f"/api/history?retailer={encoded_retailer}&product_retailer={encoded_retailer}&product_name=__definitely_missing__&max_files=1",
    )
    assert isinstance(product_empty["data"].get("history"), list), "product history must include history list"
    summary = product_empty["data"].get("summary")
    assert isinstance(summary, dict), "product history must include summary mapping"
    assert {"latest_price", "cheapest_price", "cheapest_date", "change_since_first_pct"}.issubset(summary), (
        "product history summary keys missing"
    )

    invalid = _get(client, "/api/history?retailer=Unknown%20Retailer&max_files=1", expected_status="400 Bad Request")
    assert invalid["data"] is None, "invalid filter data must be null"
    assert invalid["errors"], "invalid filter response must include errors"
    error = invalid["errors"][0]
    assert error.get("code") == "invalid_filter", "invalid filter code mismatch"
    assert isinstance(error.get("message"), str) and 0 < len(error["message"]) <= 160, "invalid error message"

    _assert_catalog(client)
    print("PASS endpoint smoke: all data, product, catalog, monthly and invalid-filter routes")


def _assert_catalog(client: Any) -> None:
    """Catalog routes: groups, a search, the first hit's item page, deals and a bad sort (400)."""
    groups = _get(client, "/api/catalog/groups")
    assert isinstance(groups["data"], list), "catalog groups data must be an array"
    search = _get(client, "/api/catalog/search?q=s%C3%BCt&limit=3")
    assert isinstance(search["data"], list) and "total" in search["meta"], "catalog search shape mismatch"
    if search["data"]:
        item = _get(client, f"/api/catalog/item?key={quote(search['data'][0]['key'], safe='')}")
        assert {"offers", "summary"} <= set(item["data"]), "catalog item keys missing"
    deals = _get(client, "/api/catalog/deals?limit=3")
    assert isinstance(deals["data"], list), "catalog deals data must be an array"
    bad = _get(client, "/api/catalog/search?sort=__bad__", expected_status="400 Bad Request")
    assert bad["errors"][0].get("code") == "invalid_filter", "catalog bad sort code mismatch"


def main() -> int:
    """Run all checks; any failure raises AssertionError."""
    _assert_import_boundaries()
    _assert_source_contracts()
    run_endpoint_smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
