from __future__ import annotations

from pathlib import Path

import pytest
from falcon import testing

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
