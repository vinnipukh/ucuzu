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
    # One store, several products under the same name: k3 is cheapest but older.
    _write(raw / "01_Food" / "Kale" / "k_2026-01-05.csv", "product_id,product_name,price\nk3,Sütaş Süt 1 L,25\n")
    _write(
        raw / "01_Food" / "Kale" / "k_2026-01-10.csv",
        "product_id,product_name,price\nk1,Sütaş Süt 1 L,33\nk2,Sütaş Süt 1 L,31\n",
    )
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


def _item_id(client: testing.TestClient, query: str) -> int:
    """ID of the first search hit for ``query``."""
    return client.simulate_get("/api/catalog/search", params={"q": query}).json["data"][0]["id"]


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
    assert isinstance(item["id"], int) and item["family_id"] is None
    assert item["store_count"] == 3
    # Kale's 25 is an older offer than its newest date: only k1/k2 (33, 31) count.
    assert item["min_price"] == 30.0
    assert item["max_price"] == 35.0
    assert item["offer_count"] == 4
    assert item["store"] == "Gurmar"
    assert item["stores"] == ["Gurmar", "Kale", "Onur"]
    assert item["max_drop_percent"] == 25.0


def test_search_excludes_stale_offers_and_rejects_bad_sort(client: testing.TestClient, catalog_db: Path) -> None:
    assert client.simulate_get("/api/catalog/search", params={"q": "peynir"}).json["data"] == []
    bad = client.simulate_get("/api/catalog/search", params={"sort": "random"})
    assert bad.status_code == 400
    assert bad.json["errors"][0]["code"] == "invalid_filter"


def test_item_lists_offers_cheapest_first_with_history(client: testing.TestClient, catalog_db: Path) -> None:
    item_id = _item_id(client, "süt")
    result = client.simulate_get("/api/catalog/item", params={"id": item_id})

    assert result.status_code == 200
    assert result.json["meta"] == {"id": item_id, "offer_count": 4}
    data = result.json["data"]
    assert (data["id"], data["match_key"], data["pack_options"]) == (item_id, "|sut sutas|||1000ml", [])
    assert [o["store"] for o in data["offers"]] == ["Gurmar", "Kale", "Onur", "Sariyer"]
    assert data["offers"][3]["is_current"] is False
    assert data["offers"][0]["history"] == [["2026-01-01", 40.0], ["2026-01-10", 30.0]]
    assert data["offers"][0]["other_offers"] == []
    assert data["summary"]["min_price"] == 30.0
    assert data["summary"]["current_offer_count"] == 3
    assert data["summary"]["lowest_ever"] == {"price": 20.0, "date": "2025-10-01", "store": "Sariyer"}


def test_item_shows_each_stores_cheapest_offer_on_its_newest_date(
    client: testing.TestClient, catalog_db: Path
) -> None:
    offers = client.simulate_get("/api/catalog/item", params={"id": _item_id(client, "süt")}).json["data"]["offers"]
    kale = next(o for o in offers if o["store"] == "Kale")

    # k3 (25) is cheaper but last seen on 2026-01-05, before Kale's newest date.
    assert (kale["product_id"], kale["latest_price"], kale["last_date"]) == ("k2", 31.0, "2026-01-10")
    assert kale["history"] == [["2026-01-10", 31.0]]
    others = [(o["product_id"], o["latest_price"], o["last_date"]) for o in kale["other_offers"]]
    assert others == [("k1", 33.0, "2026-01-10"), ("k3", 25.0, "2026-01-05")]
    assert all("history" not in o and "other_offers" not in o for o in kale["other_offers"])


def test_store_offers_never_prefers_an_unpriced_offer() -> None:
    def offer(product_id: str, price: float | None, date: str) -> dict[str, object]:
        return {"retailer": "Markets / X", "product_id": product_id, "latest_price": price, "last_date": date}

    [best] = sqlite_catalog_repository._store_offers(
        [offer("a", None, "2026-01-10"), offer("b", 12.0, "2026-01-09"), offer("c", 11.0, "2026-01-09")]
    )
    assert best["product_id"] == "c"
    assert [o["product_id"] for o in best["other_offers"]] == ["b", "a"]


def test_item_unknown_or_invalid_id(client: testing.TestClient, catalog_db: Path) -> None:
    result = client.simulate_get("/api/catalog/item", params={"id": "999999"})
    assert result.status_code == 404
    assert result.json["errors"][0]["code"] == "not_found"
    for params, message in (({}, "id is required"), ({"id": "süt"}, "Invalid id"), ({"id": "0"}, "Invalid id")):
        bad = client.simulate_get("/api/catalog/item", params=params)
        assert (bad.status_code, bad.json["errors"][0]["message"]) == (400, message)


def test_deals_and_groups(client: testing.TestClient, catalog_db: Path) -> None:
    deals = client.simulate_get("/api/catalog/deals").json["data"]
    assert [(d["store"], d["drop_percent"], d["pack"]) for d in deals] == [("Gurmar", 25.0, 1)]
    assert deals[0]["item_id"] == _item_id(client, "süt")

    groups = client.simulate_get("/api/catalog/groups").json["data"]
    assert [g["group"] for g in groups] == ["Markets"]
    assert {s["store"]: s["offer_count"] for s in groups[0]["stores"]} == {"Gurmar": 2, "Kale": 3, "Onur": 1}


@pytest.fixture
def case_price_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """BizimMarket sells whole cases: its water is "cheaper" than Onur's and its cola has no peer."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_database

    raw = tmp_path / "data" / "raw"
    _write(raw / "01_Food" / "BizimMarket" / "b_2026-01-01.csv", "product_name,price\nSu 1 L,9\nKola 250 ml,3\n")
    _write(raw / "01_Food" / "BizimMarket" / "b_2026-01-10.csv", "product_name,price\nSu 1 L,5\nKola 250 ml,3\n")
    _write(raw / "01_Food" / "Onur" / "o_2026-01-10.csv", "product_name,price\nSu 1 L,8\nÇay 1 kg,4\n")
    db_path = tmp_path / "prices.db"
    build_database.build(tmp_path / "data", db_path, workers=1)
    monkeypatch.setenv("PRICES_DB_PATH", str(db_path))
    clear_inventory_cache()
    sqlite_catalog_repository.clear_catalog_cache()
    yield db_path
    clear_inventory_cache()
    sqlite_catalog_repository.clear_catalog_cache()
    sqlite_price_repository.close_local_connections()


def test_case_prices_never_rank_cheapest(client: testing.TestClient, case_price_db: Path) -> None:
    [water] = client.simulate_get("/api/catalog/search", params={"q": "su"}).json["data"]
    assert (water["min_price"], water["max_price"], water["store"]) == (8.0, 8.0, "Onur")
    assert water["stores"] == ["Onur", "BizimMarket"]
    assert water["offer_count"] == 2

    # BizimMarket's cola (3) is the cheapest price but only a case price: it sorts last.
    by_price = client.simulate_get("/api/catalog/search", params={"sort": "price_asc"}).json["data"]
    assert [(i["name"], i["min_price"]) for i in by_price] == [("Çay 1 kg", 4.0), ("Su 1 L", 8.0), ("Kola 250 ml", 3.0)]

    item = client.simulate_get("/api/catalog/item", params={"id": water["id"]}).json["data"]
    assert [(o["store"], o["is_case_price"]) for o in item["offers"]] == [("Onur", False), ("BizimMarket", True)]
    assert item["summary"]["min_price"] == 8.0
    assert item["summary"]["lowest_ever"] == {"price": 8.0, "date": "2026-01-10", "store": "Onur"}

    # BizimMarket's 9 -> 5 drop is not a deal.
    assert client.simulate_get("/api/catalog/deals").json["data"] == []


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


@pytest.fixture
def family_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Pınar milk in 1 L (also a 6 x 1 L pack) and 500 ml: one family of two items with a pack option."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import build_database

    raw = tmp_path / "data" / "raw"
    _write(
        raw / "01_Food" / "Onur" / "o_2026-01-10.csv",
        "product_name,price\nPınar Süt 1 L,30\nPınar Süt 6x1 L,170\nPınar Süt 500 ml,18\n",
    )
    _write(raw / "01_Food" / "Gurmar" / "g_2026-01-10.csv", "product_name,price\nPINAR SÜT 1 Lt,32\nPınar Süt 1 L x 6,180\n")
    db_path = tmp_path / "prices.db"
    build_database.build(tmp_path / "data", db_path, workers=1)
    monkeypatch.setenv("PRICES_DB_PATH", str(db_path))
    clear_inventory_cache()
    sqlite_catalog_repository.clear_catalog_cache()
    yield db_path
    clear_inventory_cache()
    sqlite_catalog_repository.clear_catalog_cache()
    sqlite_price_repository.close_local_connections()


def test_multipacks_are_pack_options_and_sizes_form_a_family(client: testing.TestClient, family_db: Path) -> None:
    items = client.simulate_get("/api/catalog/search", params={"q": "pınar süt", "sort": "price_asc"}).json["data"]
    assert [(i["name"], i["min_price"], i["store_count"], i["offer_count"]) for i in items] == [
        ("Pınar Süt 500 ml", 18.0, 1, 1),
        ("Pınar Süt 1 L", 30.0, 2, 2),  # the 6-packs are not offers
    ]
    family_id = items[0]["family_id"]
    assert family_id is not None and items[1]["family_id"] == family_id

    item = client.simulate_get("/api/catalog/item", params={"id": items[1]["id"]}).json["data"]
    assert (item["family_id"], item["family_item_count"]) == (family_id, 2)
    assert [o["store"] for o in item["offers"]] == ["Onur", "Gurmar"]
    [six] = item["pack_options"]
    assert (six["pack"], six["min_price"], six["min_price_per_package"]) == (6, 170.0, 28.33)
    assert [(o["store"], o["latest_price"], o["price_per_package"]) for o in six["offers"]] == [
        ("Onur", 170.0, 28.33),
        ("Gurmar", 180.0, 30.0),
    ]
    assert all("history" not in o for o in six["offers"])

    family = client.simulate_get("/api/catalog/search", params={"family": family_id}).json
    assert family["meta"]["family"] == family_id
    assert {i["id"] for i in family["data"]} == {i["id"] for i in items}
    assert client.simulate_get("/api/catalog/search", params={"family": "x"}).status_code == 400
