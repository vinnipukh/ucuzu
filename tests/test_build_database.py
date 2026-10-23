from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_database  # noqa: E402
import data_files  # noqa: E402


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("gurmar_prices_2026-02-21.csv", "2026-02-21"),
        ("watsons_16-10-2026.csv", "2026-10-16"),
        ("onur_01.09.2026.csv", "2026-09-01"),
        ("rent_2026_03_05.csv", "2026-03-05"),
        ("snapshot_20260704.csv", "2026-07-04"),
        ("technologyProducts5-10-.csv", None),
        ("catalog.csv", None),
        ("bad_2026-13-45.csv", None),
        # Month-day names: the first occurrence on or after SCRAPE_START (2026-02-23).
        ("products10-19.csv", "2026-10-19"),
        ("products-02-23.csv", "2026-02-23"),
        ("Clothes3-10.csv", "2026-03-10"),
        ("sehirhatlari_fares_5-31.csv", "2026-05-31"),
        ("HomeGoods1-5.csv", "2027-01-05"),
        ("products2-22.csv", "2027-02-22"),
        ("products2-29.csv", None),
        ("products13-1.csv", None),
        ("health_prices_2026-03.csv", None),
        ("products10-19-2.csv", None),
    ],
)
def test_parse_file_date(name: str, expected: str | None) -> None:
    assert build_database.parse_file_date(name) == expected


@pytest.mark.parametrize(
    ("dirs", "expected"),
    [
        (("01_Food", "Gurmar"), "Markets / Gurmar"),
        (("03_Clothing", "Bershka", "ProductData"), "ClothingStores / Bershka"),
        (("04_Housing", "Kayseri"), "HousesRent / Kayseri"),
        (("04_Housing", "Duzce_Kocaeli_Sakarya", "Duzce"), "HousesRent / Duzce"),
        (("05_Furnishings", "ConstructionSuppliesMarkets", "yapimaks"), "ConstructionSuppliesMarkets / yapimaks"),
        (("05_Furnishings", "HomeGoods", "Chakra"), "HomeGoods / Chakra"),
        (("13_Personal_Care", "Cosmetics", "Watson"), "Cosmetics / Watson"),
        (("06_Health", "Diagnostic&Surgical Services"), "Health / Diagnostic&Surgical Services"),
        (("02_Alcohol_Tobacco", "Karekod"), "Alcohol Tobacco / Karekod"),
        (("04_Housing",), "HousesRent"),
        (("EpeyKatfg",), "EpeyKatfg"),
        ((), None),
    ],
)
def test_raw_retailer_label(dirs: tuple[str, ...], expected: str | None) -> None:
    assert build_database.raw_retailer_label(dirs) == expected


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (["İsim", "Fiyat"], ["name", "Fiyat"]),  # "Fiyat" is already a canonical price column
        (["isim", "fiyat"], ["name", "price"]),
        (["Tarih", "UrunID", "UrunAdi", "FiyatFloat"], ["Tarih", "UrunID", "name", "price"]),
        (["ana_kategori", "ad", "fiyat", "normal_fiyat"], ["category", "name", "price", "normal_fiyat"]),
        (["Category", "Name", "Current Price", "Original Price"], ["Category", "name", "price", "Original Price"]),
        # Category and id aliases (A101, Cagri, Macrocenter, GoldenRose, Altınyıldız layouts).
        (
            ["ana_kategori", "alt_kategori", "marka", "ad", "fiyat", "urun_id", "barkod"],
            ["category", "alt_kategori", "marka", "name", "price", "product_id", "barkod"],
        ),
        (["category", "product_name", "price_tl", "product_code"], ["category", "product_name", "price", "product_id"]),
        (["Category", "Subcategory", "Name", "Brand", "SKU", "Price"], ["Category", "Subcategory", "name", "Brand", "product_id", "Price"]),
        (["Product ID", "SKU", "Category Path", "Full Category"], ["Product ID", "product_id", "Category Path", "category"]),
        (["id", "urun", "fiyat", "kategori"], ["id", "name", "price", "category"]),
        # TÜİK codes are not shop categories.
        (["product_name", "price", "category_number", "sub_category_number"], ["product_name", "price", "category_number", "sub_category_number"]),
        (["product_name", "price (TL)"], ["product_name", "price"]),
        (["Brand", "productName", "Price"], ["Brand", "name", "Price"]),
        (["product_id", "name", "regular_price", "sale_price"], ["product_id", "name", "regular_price", "price"]),
        # Canonical columns already present: nothing is renamed.
        (["product-name", "product_price", "Ürün Adı"], ["product-name", "product_price", "Ürün Adı"]),
    ],
)
def test_normalize_columns(columns: list[str], expected: list[str]) -> None:
    frame = build_database.normalize_columns(pd.DataFrame(columns=columns))
    assert list(frame.columns) == expected


def test_build_end_to_end(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "01_Food" / "Gurmar"
    raw.mkdir(parents=True)
    (raw / "gurmar_prices_2026-01-01.csv").write_text("product-name;product-price\nMilk;10,00\nBread;5\n", encoding="utf-8")
    (raw / "gurmar_prices_2026-01-02.csv").write_text("product_name,price\nMilk,\"12,50\"\n", encoding="utf-8")
    (raw / "notes.csv").write_text("x\n1\n", encoding="utf-8")
    json_dir = tmp_path / "prices_json"
    json_dir.mkdir()
    (json_dir / "Markets_Gurmar.json").write_text('{"Old": {"name": "Old", "prices": {"2025-01-01": 1}}}', encoding="utf-8")
    (json_dir / "Technology.json").write_text(
        '{"t1": {"name": "Phone", "category": "Phones", "prices": {"2026-01-01": 100, "2026-01-05": 90}}}',
        encoding="utf-8",
    )
    db_path = tmp_path / "prices.db"

    build_database.build(tmp_path, db_path, workers=1)

    with sqlite3.connect(db_path) as conn:
        products = {
            row[0]: row[1:]
            for row in conn.execute(
                "SELECT retailer || '|' || product_id, first_price_check, latest_price, observations_count FROM ("
                "SELECT *, json_extract(price_history, '$.\"2026-01-01\"') AS first_price_check FROM product_prices)"
            )
        }
        ledger = conn.execute("SELECT file_path, retailer, date, rows_ingested FROM ingested_files ORDER BY file_path").fetchall()
    # CSV-covered retailer ignores its stale JSON; uncovered JSON retailer is filled in.
    assert products == {
        "Markets / Gurmar|Milk": (10.0, 12.5, 2),
        "Markets / Gurmar|Bread": (5.0, 5.0, 1),
        "Technology|t1": (100.0, 90.0, 2),
    }
    assert ledger == [
        ("Technology.json#2026-01-01", "Technology", "2026-01-01", 1),
        ("Technology.json#2026-01-05", "Technology", "2026-01-05", 1),
        ("raw/01_Food/Gurmar/gurmar_prices_2026-01-01.csv", "Markets / Gurmar", "2026-01-01", 2),
        ("raw/01_Food/Gurmar/gurmar_prices_2026-01-02.csv", "Markets / Gurmar", "2026-01-02", 1),
    ]
    assert not Path(f"{db_path}.building").exists()


def test_build_dedupes_days_and_keeps_latest_name(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "01_Food" / "Kim"
    raw.mkdir(parents=True)
    (raw / "kim_2026-01-01.csv").write_text("product_id,name,price\n7,Old Name,10\n", encoding="utf-8")
    # A second scrape of the same day: the later file wins, as with INSERT OR REPLACE.
    (raw / "kim_2026-01-01_rerun.csv").write_text("product_id,name,price\n7,Old Name,11\n", encoding="utf-8")
    (raw / "kim_2026-01-03.csv").write_text("product_id,name,price\n7,New Name,12\n", encoding="utf-8")
    db_path = tmp_path / "prices.db"

    build_database.build(tmp_path, db_path, workers=1)

    with sqlite3.connect(db_path) as conn:
        observations = conn.execute(
            "SELECT date, product_id, product_name, price FROM price_observations ORDER BY date"
        ).fetchall()
        product = conn.execute(
            "SELECT product_name, first_date, last_date, latest_price, min_price, max_price, observations_count "
            "FROM product_prices"
        ).fetchone()
        without_rowid = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'observations'").fetchone()[0]
    assert observations == [("2026-01-01", "7", "New Name", 11.0), ("2026-01-03", "7", "New Name", 12.0)]
    assert product == ("New Name", "2026-01-01", "2026-01-03", 12.0, 11.0, 12.0, 2)
    assert "WITHOUT ROWID" in without_rowid
    assert not [p.name for p in tmp_path.iterdir() if ".building" in p.name or ".staging" in p.name]


def test_build_stores_catalog_columns(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "01_Food" / "Kim"
    raw.mkdir(parents=True)
    (raw / "kim_2026-01-01.csv").write_text(
        "product_id,name,price\n7,ÇAY 500 G,10\n8,Su,5\n9,Çay 500 g,9\n", encoding="utf-8"
    )
    (raw / "kim_2026-01-02.csv").write_text("product_id,name,price\n7,ÇAY 500 G,10\n", encoding="utf-8")
    (raw / "kim_2026-01-03.csv").write_text("product_id,name,price\n7,ÇAY 500 G,8\n", encoding="utf-8")
    db_path = tmp_path / "prices.db"

    build_database.build(tmp_path, db_path, workers=1)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT product_id, name_key, latest_price, previous_price, price_since, is_current, is_store_latest "
            "FROM products ORDER BY product_id"
        ).fetchall()
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    # The price changed on 01-03 (10 -> 8); Su was last seen two days before Kim's newest file.
    # Product 9 shares 7's name_key but was last seen earlier, so it is not Kim's latest price for it.
    assert rows == [
        ("7", "çay 500g", 8.0, 10.0, "2026-01-03", 1, 1),
        ("8", "su", 5.0, None, "2026-01-01", 1, 1),
        ("9", "çay 500g", 9.0, None, "2026-01-01", 1, 0),
    ]
    assert "idx_products_name_key" in indexes


def test_split_and_join_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_files, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(data_files, "GITIGNORE", tmp_path / ".gitignore")
    monkeypatch.setattr(data_files, "LIMIT_MB", 1)
    monkeypatch.setattr(data_files, "CHUNK_MB", 1)
    data = tmp_path / "data"
    data.mkdir()
    big = data / "big.csv"
    payload = bytes(range(256)) * (10 * 1024)  # 2.5 MiB
    big.write_bytes(payload)
    (tmp_path / ".gitignore").write_text("*.db\n", encoding="utf-8")

    assert data_files.check(data) == 1
    data_files.split(data)
    assert sorted(p.name for p in data.glob("big.csv.part*")) == ["big.csv.part001", "big.csv.part002", "big.csv.part003"]
    assert "/data/big.csv" in (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert data_files.check(data) == 0

    big.unlink()
    data_files.join(data)
    assert big.read_bytes() == payload
    # Re-splitting keeps a single managed .gitignore block.
    data_files.split(data)
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8").count(data_files.BLOCK_START) == 1


def test_build_stores_product_details_and_unit_prices(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "01_Food" / "A101"
    raw.mkdir(parents=True)
    header = "urun_id,marka,ad,fiyat,normal_fiyat,barkod,resim_url,url\n"
    (raw / "a101_2026-01-01.csv").write_text(
        header
        + "1,Pınar,Pınar Süt 1 L,50,60,8690526010000,https://a.com/1.jpg,https://a.com/1\n"
        + "2,,Yumurta 30'lu,150,,,,\n"
        + "3,,Oje 112,40,,,,\n",
        encoding="utf-8",
    )
    # The regular price of product 1 was only sent on the first day, so it is not current.
    (raw / "a101_2026-01-02.csv").write_text(header + "1,Pınar,Pınar Süt 1 L,45,,,,\n", encoding="utf-8")
    db_path = tmp_path / "prices.db"

    build_database.build(tmp_path, db_path, workers=1)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT product_id, brand, barcode, image_url, product_url, regular_price, unit_price, unit_price_unit "
            "FROM products ORDER BY product_id"
        ).fetchall()
    assert rows == [
        ("1", "Pınar", "8690526010000", "https://a.com/1.jpg", "https://a.com/1", None, pytest.approx(0.045), "ml"),
        ("2", None, None, None, None, None, pytest.approx(5.0), "adet"),
        ("3", None, None, None, None, None, None, None),
    ]
