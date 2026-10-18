from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from falcon import testing

from inflation_dashboard.adapters import sqlite_catalog_repository, sqlite_price_repository
from inflation_dashboard.api.falcon_app import create_app
from inflation_dashboard.api.filters import clear_inventory_cache
from inflation_dashboard.domain.catalog import name_key, search_terms, split_retailer


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("SÜTAŞ Süt 1 L", "sütaş süt 1l"),
        ("Sütaş  süt 1l", "sütaş süt 1l"),
        ("IŞIK Ayran 0,5 lt", "ışık ayran 0.5lt"),
        ("İnci Un 500 g.", "inci un 500g"),
        ("Çay - Rize (Siyah)", "çay rize siyah"),
    ],
)
def test_name_key(name: str, expected: str) -> None:
    assert name_key(name) == expected


def test_search_terms_use_the_same_normalization() -> None:
    assert search_terms("  SÜT 1 L ") == ["süt", "1l"]


def test_split_retailer() -> None:
    assert split_retailer("Markets / Migros") == ("Markets", "Migros")
    assert split_retailer("EpeyKatfg") == ("EpeyKatfg", "EpeyKatfg")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def catalog_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Two current markets sell the same milk (spelled differently); Gurmar cuts its price."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_database

    raw = tmp_path / "data" / "raw"
    _write(raw / "01_Food" / "Gurmar" / "g_2026-01-01.csv", "product_name,price\nSÜTAŞ Süt 1 L,40\nEkmek,10\n")
    _write(raw / "01_Food" / "Gurmar" / "g_2026-01-10.csv", "product_name,price\nSÜTAŞ Süt 1 L,30\nEkmek,10\n")
    _write(raw / "01_Food" / "Onur" / "o_2026-01-10.csv", "product_name,price\nSütaş süt 1l,35\n")
    # Seen only long before Onur's newest file: not current.
    _write(raw / "01_Food" / "Onur" / "o_2025-12-01.csv", "product_name,price\nEski Peynir,99\n")
    # A store whose scraping stopped long before the newest date: not current, even at 20.
    _write(raw / "01_Food" / "Sariyer" / "s_2025-10-01.csv", "product_name,price\nSütaş Süt 1 L,20\n")
    _write(raw / "04_Housing" / "Ankara" / "a_2026-01-10.csv", "product_name,price\nSüt Mahallesi,5000\n")
    db_path = tmp_path / "prices.db"
    build_database.build(tmp_path / "data", db_path, workers=1)
    monkeypatch.setenv("PRICES_DB_PATH", str(db_path))
    clear_inventory_cache()
    sqlite_catalog_repository.clear_catalog_cache()
    yield db_path
    clear_inventory_cache()
    sqlite_catalog_repository.clear_catalog_cache()
    sqlite_price_repository.close_local_connections()


@pytest.fixture
def client() -> testing.TestClient:
    return testing.TestClient(create_app())


def test_build_stores_price_change_and_current_flag(catalog_db: Path) -> None:
    conn = sqlite3.connect(catalog_db)
    rows = {
        name: (key, latest, previous, since, current)
        for name, key, latest, previous, since, current in conn.execute(
            "SELECT product_name, name_key, latest_price, previous_price, price_since, is_current FROM products"
        )
    }
    conn.close()
    assert rows["SÜTAŞ Süt 1 L"] == ("sütaş süt 1l", 30.0, 40.0, "2026-01-10", 1)
    assert rows["Ekmek"] == ("ekmek", 10.0, None, "2026-01-01", 1)
    assert rows["Eski Peynir"][4] == 0


def test_search_groups_offers_across_stores(client: testing.TestClient, catalog_db: Path) -> None:
    result = client.simulate_get("/api/catalog/search", params={"q": "süt"})

    assert result.status_code == 200
    assert result.json["meta"]["total"] == 1  # housing listings are not in the catalog
    item = result.json["data"][0]
    assert item["key"] == "sütaş süt 1l"
    assert item["store_count"] == 2
    assert item["min_price"] == 30.0
    assert item["max_price"] == 35.0
    assert item["store"] == "Gurmar"
    assert item["max_drop_percent"] == 25.0


def test_search_excludes_stale_offers_and_rejects_bad_sort(client: testing.TestClient, catalog_db: Path) -> None:
    assert client.simulate_get("/api/catalog/search", params={"q": "peynir"}).json["data"] == []
    bad = client.simulate_get("/api/catalog/search", params={"sort": "random"})
    assert bad.status_code == 400
    assert bad.json["errors"][0]["code"] == "invalid_filter"


def test_item_lists_offers_cheapest_first_with_history(client: testing.TestClient, catalog_db: Path) -> None:
    result = client.simulate_get("/api/catalog/item", params={"key": "sütaş süt 1l"})

    assert result.status_code == 200
    data = result.json["data"]
    assert [o["store"] for o in data["offers"]] == ["Gurmar", "Onur", "Sariyer"]
    assert data["offers"][2]["is_current"] is False
    assert data["offers"][0]["history"] == [["2026-01-01", 40.0], ["2026-01-10", 30.0]]
    assert data["summary"]["min_price"] == 30.0
    assert data["summary"]["lowest_ever"] == {"price": 20.0, "date": "2025-10-01", "store": "Sariyer"}


def test_item_unknown_key_is_not_found(client: testing.TestClient, catalog_db: Path) -> None:
    result = client.simulate_get("/api/catalog/item", params={"key": "yok"})
    assert result.status_code == 404
    assert result.json["errors"][0]["code"] == "not_found"


def test_deals_and_groups(client: testing.TestClient, catalog_db: Path) -> None:
    deals = client.simulate_get("/api/catalog/deals").json["data"]
    assert [(d["store"], d["drop_percent"]) for d in deals] == [("Gurmar", 25.0)]

    groups = client.simulate_get("/api/catalog/groups").json["data"]
    assert [g["group"] for g in groups] == ["Markets"]
    assert {s["store"]: s["offer_count"] for s in groups[0]["stores"]} == {"Gurmar": 2, "Onur": 1}


def test_outdated_database_returns_503(client: testing.TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE retailers (retailer_key INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE products (product_key INTEGER PRIMARY KEY, retailer_key INTEGER, product_name TEXT);"
    )
    conn.close()
    monkeypatch.setenv("PRICES_DB_PATH", str(db_path))
    sqlite_catalog_repository.clear_catalog_cache()
    try:
        result = client.simulate_get("/api/catalog/groups")
    finally:
        sqlite_price_repository.close_local_connections()
        sqlite_catalog_repository.clear_catalog_cache()

    assert result.status_code == 503
    assert result.json["errors"][0]["code"] == "database_outdated"
