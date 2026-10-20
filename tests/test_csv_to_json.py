from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_database  # noqa: E402
import csv_to_json  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _observations(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            """SELECT r.name, p.product_id, p.product_name, c.name, o.date, o.price
               FROM observations o JOIN products p USING (product_key)
               JOIN retailers r USING (retailer_key) JOIN categories c ON c.category_key = p.category_key
               ORDER BY 1, 2, 5"""
        ).fetchall()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Two stores: Kim (renames a product, two files on one day) and an undated leftover."""
    data = tmp_path / "data"
    kim = data / "raw" / "01_Food" / "Kim"
    _write(kim / "kim_2026-01-01.csv", "product_id,name,category,price\n7,Çay,İçecek,10\n8,Su,İçecek,5\n")
    _write(kim / "kim_2026-01-02.csv", "product_id,name,category,price\n7,Çay 500 g,Sıcak,11\n")
    _write(kim / "kim_tech_2026-01-02.csv", "product_id,name,category,price\n7,Çay 500 g,Sıcak,12\n")
    _write(kim / "kim_all_products.csv", "product_id,name,price\n7,Çay,1\n")  # undated: the build skips it
    _write(data / "raw" / "10_Education" / "Open_Education" / "oe_2026-01-02.csv", "name,price\nKurs,100\n")
    return data


def test_converted_json_builds_the_same_database(data_dir: Path, tmp_path: Path) -> None:
    build_database.build(data_dir, tmp_path / "before.db", workers=1)
    labels = {"Markets / Kim", "Education / Open_Education"}

    assert csv_to_json.convert(data_dir, [], labels, workers=1) == 0
    build_database.build(data_dir, tmp_path / "after.db", workers=1)

    assert _observations(tmp_path / "after.db") == _observations(tmp_path / "before.db")
    # Converted CSVs are gone; the undated file the build never read stays.
    assert sorted(p.name for p in (data_dir / "raw").rglob("*.csv")) == ["kim_all_products.csv"]
    assert not (data_dir / "raw" / "10_Education").exists()
    kim = json.loads((data_dir / "prices_json" / "Markets_Kim.json").read_text(encoding="utf-8"))
    # Last file of the day wins (kim_tech sorts after kim_), name/category from the newest row.
    assert kim["7"] == {
        "name": "Çay 500 g",
        "category": "Sıcak",
        "latest_price": 12.0,
        "min_price": 10.0,
        "max_price": 12.0,
        "prices": {"2026-01-01": 10.0, "2026-01-02": 12.0},
    }
    assert (data_dir / "prices_json" / "Education_Open_Education.json").exists()


def test_source_import_adds_new_prices_without_overwriting(data_dir: Path, tmp_path: Path) -> None:
    assert csv_to_json.convert(data_dir, [], {"Markets / Kim"}, workers=1) == 0
    upstream = tmp_path / "upstream"
    # A re-scrape of 01-02 with another price (ignored), a new day, and a dropped store.
    _write(upstream / "01_Food" / "Kim" / "kim_2026-01-02.csv", "product_id,name,price\n7,Çay 500 g,99\n")
    _write(upstream / "01_Food" / "Kim" / "kim_2026-01-03.csv", "product_id,name,price\n7,Çay 1 kg,13\n9,Süt,20\n")
    _write(upstream / "08_Communication" / "Xiaomi" / "x_2026-01-03.csv", "name,price\nTelefon,5000\n")

    assert csv_to_json.convert(data_dir, [upstream], None, workers=1) == 0

    kim = json.loads((data_dir / "prices_json" / "Markets_Kim.json").read_text(encoding="utf-8"))
    assert kim["7"]["prices"] == {"2026-01-01": 10.0, "2026-01-02": 12.0, "2026-01-03": 13.0}
    assert kim["7"]["name"] == "Çay 1 kg"  # newer upstream row renames the product
    assert kim["9"]["prices"] == {"2026-01-03": 20.0}
    assert not (data_dir / "prices_json" / "Communication_Xiaomi.json").exists()


def test_source_import_folds_in_remaining_raw_csvs(data_dir: Path, tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    _write(upstream / "01_Food" / "Kim" / "kim_2026-01-01.csv", "product_id,name,price\n7,Çay,77\n")

    assert csv_to_json.convert(data_dir, [upstream], None, workers=1) == 0

    kim = json.loads((data_dir / "prices_json" / "Markets_Kim.json").read_text(encoding="utf-8"))
    assert kim["7"]["prices"]["2026-01-01"] == 10.0  # this repository's CSV beats upstream
    assert not (data_dir / "raw" / "01_Food" / "Kim" / "kim_2026-01-01.csv").exists()


def test_dry_run_changes_nothing(data_dir: Path) -> None:
    before = sorted(p.relative_to(data_dir) for p in data_dir.rglob("*"))
    assert csv_to_json.convert(data_dir, [], {"Markets / Kim"}, workers=1, dry_run=True) == 0
    assert sorted(p.relative_to(data_dir) for p in data_dir.rglob("*")) == before


def test_unknown_retailer_is_an_error(data_dir: Path) -> None:
    assert csv_to_json.convert(data_dir, [], {"Markets / Nope"}, workers=1) == 1


@pytest.mark.parametrize(
    ("stem", "label"),
    [
        ("Markets_Gurmar", "Markets / Gurmar"),
        ("Education_Open_Education", "Education / Open_Education"),
        ("Transport_motor_bicyle_car", "Transport / motor_bicyle_car"),
        ("Health_Diagnostic_Surgical_Services", "Health / Diagnostic&Surgical Services"),
        ("EpeyKatfg", "EpeyKatfg"),
    ],
)
def test_retailer_stem_round_trip(stem: str, label: str) -> None:
    assert build_database.retailer_from_stem(stem) == label
    assert build_database.retailer_stem(label) == stem


@pytest.mark.parametrize("label", ["A / B / C", "Alcohol_Tobacco / X", "Markets / A:B"])
def test_retailer_stem_rejects_labels_that_cannot_round_trip(label: str) -> None:
    with pytest.raises(ValueError):
        build_database.retailer_stem(label)
