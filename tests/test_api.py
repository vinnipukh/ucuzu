from __future__ import annotations

from pathlib import Path

import pytest
from falcon import testing

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
