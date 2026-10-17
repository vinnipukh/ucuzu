from __future__ import annotations

import sys
from pathlib import Path

import pytest
from falcon import testing

from inflation_dashboard.adapters import sqlite_price_repository
from inflation_dashboard.api import resources
from inflation_dashboard.api.falcon_app import create_app
from inflation_dashboard.api.filters import clear_inventory_cache


@pytest.fixture
def client() -> testing.TestClient:
    clear_inventory_cache()
    yield testing.TestClient(create_app())
    clear_inventory_cache()


@pytest.fixture
def missing_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "missing.db"
    monkeypatch.setenv("PRICES_DB_PATH", str(db_path))
    return db_path


def test_inventory_returns_503_when_database_missing(client: testing.TestClient, missing_db: Path) -> None:
    result = client.simulate_get("/api/inventory")

    assert result.status_code == 503
    assert result.json["data"] is None
    assert result.json["errors"][0]["code"] == "database_unavailable"
    assert result.json["errors"][0]["message"] == "Database not found; run scripts/build_database.py"


def test_inventory_returns_503_when_database_empty(client: testing.TestClient, missing_db: Path) -> None:
    missing_db.write_bytes(b"")

    result = client.simulate_get("/api/inventory")

    assert result.status_code == 503
    assert result.json["errors"][0]["code"] == "database_unavailable"


@pytest.mark.parametrize(
    "path",
    ["/api/history", "/api/coverage", "/api/products/search?q=x", "/api/product?product_id=x"],
)
def test_data_endpoints_return_503_when_database_missing(
    client: testing.TestClient, missing_db: Path, path: str
) -> None:
    result = client.simulate_get(path)

    assert result.status_code == 503
    assert result.json["errors"][0]["code"] == "database_unavailable"


def test_health_reports_missing_database(client: testing.TestClient, missing_db: Path) -> None:
    result = client.simulate_get("/api/health")

    assert result.status_code == 200
    assert result.json["data"] == {"status": "ok", "database": "unavailable"}


def test_unknown_route_returns_not_found_envelope(client: testing.TestClient) -> None:
    result = client.simulate_get("/api/does-not-exist")

    assert result.status_code == 404
    assert set(result.json) == {"data", "meta", "errors"}
    assert result.json["errors"][0]["code"] == "not_found"


def test_unsupported_method_returns_method_not_allowed_envelope(client: testing.TestClient) -> None:
    result = client.simulate_post("/api/health")

    assert result.status_code == 405
    assert result.json["errors"][0]["code"] == "method_not_allowed"
    assert "GET" in result.headers["allow"]


def test_unhandled_exception_returns_fixed_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(self: object, req: object, resp: object) -> None:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(resources.HealthResource, "on_get", explode)
    client = testing.TestClient(create_app())

    result = client.simulate_get("/api/health")

    assert result.status_code == 500
    assert result.json["data"] is None
    assert result.json["errors"] == [{"code": "server_error", "message": "Internal server error"}]
    assert "secret internal detail" not in result.text


def test_error_responses_carry_cors_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FALCON_CORS_ORIGINS", raising=False)
    client = testing.TestClient(create_app())

    result = client.simulate_get("/api/does-not-exist", headers={"Origin": "http://example.test"})

    assert result.status_code == 404
    assert result.headers.get("access-control-allow-origin") == "*"


@pytest.fixture
def tiny_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Build a two-retailer database with scripts/build_database.py and serve from it."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_database

    raw = tmp_path / "data" / "raw" / "01_Food" / "Gurmar"
    raw.mkdir(parents=True)
    (raw / "gurmar_prices_2026-01-01.csv").write_text("product_name,price\nMilk,10\nBread,5\n", encoding="utf-8")
    (raw / "gurmar_prices_2026-01-02.csv").write_text("product_name,price\nMilk,12\n", encoding="utf-8")
    other = tmp_path / "data" / "raw" / "01_Food" / "Onur"
    other.mkdir(parents=True)
    (other / "onur_2026-01-02.csv").write_text("product_name,price\nTea,7\n", encoding="utf-8")
    db_path = tmp_path / "prices.db"
    build_database.build(tmp_path / "data", db_path, workers=1)
    monkeypatch.setenv("PRICES_DB_PATH", str(db_path))
    clear_inventory_cache()
    yield db_path
    clear_inventory_cache()
    sqlite_price_repository.close_local_connections()


def test_product_list_groups_names_by_retailer(client: testing.TestClient, tiny_db: Path) -> None:
    result = client.simulate_get("/api/products", params={"retailer": ["Markets / Gurmar", "Markets / Onur"]})

    assert result.status_code == 200
    assert result.json["data"] == [
        {"retailer": "Markets / Gurmar", "products": ["Bread", "Milk"]},
        {"retailer": "Markets / Onur", "products": ["Tea"]},
    ]
    assert result.json["meta"]["product_count"] == 3


def test_product_list_keeps_only_products_seen_in_the_date_window(
    client: testing.TestClient, tiny_db: Path
) -> None:
    result = client.simulate_get("/api/products", params={"retailer": "Markets / Gurmar", "start_date": "2026-01-02"})

    assert result.json["data"] == [{"retailer": "Markets / Gurmar", "products": ["Milk"]}]


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({}, "retailer is required"),
        ({"retailer": "Nope"}, "Unknown retailer: Nope"),
        ({"retailer": "Markets / Gurmar", "start_date": "2026-02-01", "end_date": "2026-01-01"}, "Invalid date range"),
    ],
)
def test_product_list_rejects_bad_filters(
    client: testing.TestClient, tiny_db: Path, params: dict[str, str], message: str
) -> None:
    result = client.simulate_get("/api/products", params=params)

    assert result.status_code == 400
    assert result.json["errors"] == [{"code": "invalid_filter", "message": message}]
