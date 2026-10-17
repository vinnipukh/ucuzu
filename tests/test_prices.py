from __future__ import annotations

import math

import pandas as pd
import pytest

from inflation_dashboard.domain.prices import (
    HISTORY_COLUMNS,
    build_product_frame,
    coerce_price,
    coerce_price_series,
    first_non_empty_column,
    parse_date_from_name,
)

DATE = pd.Timestamp("2026-01-15")


# --- parse_date_from_name -------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("gurmar_2026-01-15.csv", "2026-01-15"),
        ("gurmar_2026_01_15.csv", "2026-01-15"),
        ("data/raw/2025-12-31/products.csv", "2025-12-31"),
    ],
)
def test_parse_date_from_name_extracts_date(name: str, expected: str) -> None:
    assert parse_date_from_name(name) == pd.Timestamp(expected)


@pytest.mark.parametrize("name", ["products.csv", "1999-01-01.csv", "2026-13-45.csv"])
def test_parse_date_from_name_returns_nat_when_missing_or_invalid(name: str) -> None:
    assert parse_date_from_name(name) is pd.NaT


# --- coerce_price ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (12.5, 12.5),
        (7, 7.0),
        ("12.50", 12.5),
        ("12,50", 12.5),
        ("12,5", 12.5),
        ("1.234,56 TL", 1234.56),
        ("1,234.56", 1234.56),
        ("₺1.234", 1234.0),
        ("1.234.567", 1234567.0),
        ("1,234", 1234.0),
        ("1,234,567", 1234567.0),
        ("  99 TRY ", 99.0),
        ('"45,90"', 45.9),
        ("1\xa0234,50 TL", 1234.5),
        ("-3,25", -3.25),
    ],
)
def test_coerce_price_parses_formats(raw: object, expected: float) -> None:
    assert coerce_price(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, float("nan"), pd.NA, "", "   ", "nan", "None", "N/A", "TL", "-", ",", "abc"])
def test_coerce_price_returns_none_for_empty_or_junk(raw: object) -> None:
    assert coerce_price(raw) is None


# --- coerce_price_series --------------------------------------------------


def test_coerce_price_series_passes_numeric_through() -> None:
    series = pd.Series([1, 2.5, None])
    result = coerce_price_series(series)
    assert result.iloc[:2].tolist() == [1.0, 2.5]
    assert math.isnan(result.iloc[2])


PARITY_INPUTS = [
    "12.50",
    "12,50",
    "12,5",
    "1.234,56 TL",
    "1,234.56",
    "₺1.234",
    "1.234.567",
    "1,234",
    "1,234,567",
    "  99 TRY ",
    '"45,90"',
    "1\xa0234,50 TL",
    "-3,25",
    "",
    "TL",
    "-",
    "abc",
    None,
]


def test_coerce_price_series_matches_scalar_semantics() -> None:
    series = pd.Series(PARITY_INPUTS, dtype="object")
    vectorized = coerce_price_series(series).tolist()
    scalar = [coerce_price(value) for value in PARITY_INPUTS]
    for raw, vec, sca in zip(PARITY_INPUTS, vectorized, scalar):
        if sca is None:
            assert pd.isna(vec), f"{raw!r}: expected missing, got {vec!r}"
        else:
            assert vec == pytest.approx(sca), f"{raw!r}: series={vec!r} scalar={sca!r}"


# --- first_non_empty_column -----------------------------------------------


def test_first_non_empty_column_combines_in_priority_order() -> None:
    frame = pd.DataFrame({"sku": ["A1", "", None], "id": ["X", "Y", "Z"]})
    result = first_non_empty_column(frame, ["missing", "sku", "id"])
    assert result.tolist() == ["A1", "Y", "Z"]


def test_first_non_empty_column_strips_whitespace() -> None:
    frame = pd.DataFrame({"name": ["  Milk  ", "   "]})
    result = first_non_empty_column(frame, ["name"])
    assert result.iloc[0] == "Milk"
    assert pd.isna(result.iloc[1])


def test_first_non_empty_column_all_missing_columns() -> None:
    frame = pd.DataFrame({"other": [1, 2]})
    result = first_non_empty_column(frame, ["sku", "id"])
    assert len(result) == 2
    assert result.isna().all()


# --- build_product_frame --------------------------------------------------


def test_build_product_frame_default_retailer() -> None:
    frame = pd.DataFrame(
        {
            "product_id": ["p1", "p2", None, "p4"],
            "name": ["Milk", None, "Orphan", "Bad price"],
            "category": ["Dairy", None, "X", "Y"],
            "price": ["12,50 TL", "1.234,00", "5", "n/a"],
        }
    )
    result = build_product_frame(frame, "Markets / Gurmar", "price", DATE, "gurmar.csv")

    assert list(result.columns) == HISTORY_COLUMNS
    # The bad-price row is dropped; the missing name/id fall back to each other.
    assert result["product_id"].tolist() == ["p1", "p2", "Orphan"]
    assert result["product_name"].tolist() == ["Milk", "p2", "Orphan"]
    assert result["category"].tolist() == ["Dairy", "Uncategorized", "X"]
    assert result["price"].tolist() == pytest.approx([12.5, 1234.0, 5.0])
    assert (result["date"] == DATE).all()
    assert (result["retailer"] == "Markets / Gurmar").all()
    assert (result["source_file"] == "gurmar.csv").all()


def test_build_product_frame_drops_rows_without_identity() -> None:
    frame = pd.DataFrame({"product_id": [None, "  "], "name": [None, ""], "price": [1.0, 2.0]})
    result = build_product_frame(frame, "Markets / Gurmar", "price", DATE, "f.csv")
    assert result.empty
    assert list(result.columns) == HISTORY_COLUMNS


def test_build_product_frame_houses_rent() -> None:
    frame = pd.DataFrame({"District": ["Kadıköy", "Beşiktaş"], "Rooms": ["2+1", None], "Price": ["25.000", "30.000"]})
    result = build_product_frame(frame, "HousesRent / Istanbul", "Price", DATE, "rent.csv")
    assert result["product_name"].tolist() == ["Kadıköy - 2+1", "Beşiktaş"]
    assert result["product_id"].tolist() == result["product_name"].tolist()
    assert result["category"].tolist() == ["2+1", "Uncategorized"]
    assert result["price"].tolist() == [25000.0, 30000.0]


def test_build_product_frame_watsons() -> None:
    frame = pd.DataFrame({"brand": ["Nivea", None], "sku": ["S1", "S2"], "price": [10.0, 20.0]})
    result = build_product_frame(frame, "Cosmetics / Watson", "price", DATE, "w.csv")
    assert result["product_id"].tolist() == ["S1", "S2"]
    assert result["product_name"].tolist() == ["Nivea (S1)", "S2"]
    assert result["category"].tolist() == ["Nivea", "Uncategorized"]
