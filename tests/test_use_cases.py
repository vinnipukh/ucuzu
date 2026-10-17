from __future__ import annotations

import pandas as pd
import pytest

from inflation_dashboard.application.use_cases import (
    calculate_category_coverage,
    calculate_coverage_over_time,
    calculate_coverage_summary,
    calculate_price_movers,
    calculate_retailer_average_trends,
    get_product_history,
    list_inventory_filters,
    summarize_product_history,
)

from .conftest import make_history

# --- list_inventory_filters -----------------------------------------------


def test_list_inventory_filters_empty() -> None:
    assert list_inventory_filters(pd.DataFrame()) == {
        "retailers": [],
        "min_date": None,
        "max_date": None,
        "file_count": 0,
    }


def test_list_inventory_filters_sorts_and_dedupes_retailers() -> None:
    inventory = pd.DataFrame(
        {
            "retailer": ["B", "A", "B", None],
            "date": pd.to_datetime(["2026-01-02", "2026-01-01", "2026-01-05", "2026-01-03"]),
        }
    )
    result = list_inventory_filters(inventory)
    assert result["retailers"] == ["A", "B"]
    assert result["min_date"] == pd.Timestamp("2026-01-01")
    assert result["max_date"] == pd.Timestamp("2026-01-05")
    assert result["file_count"] == 4


# --- get_product_history / summarize_product_history ----------------------


def test_get_product_history_filters_and_sorts(history: pd.DataFrame) -> None:
    shuffled = history.sample(frac=1, random_state=0)
    result = get_product_history(shuffled, "Markets / A", "Milk")
    assert result["price"].tolist() == [10.0, 12.0, 15.0]
    assert result["date"].is_monotonic_increasing


def test_get_product_history_no_match(history: pd.DataFrame) -> None:
    assert get_product_history(history, "Markets / B", "Milk").empty


def test_summarize_product_history_empty() -> None:
    assert summarize_product_history(pd.DataFrame(columns=["date", "price"])) == {
        "latest_price": None,
        "cheapest_price": None,
        "cheapest_date": None,
        "change_since_first_pct": 0.0,
    }


def test_summarize_product_history(history: pd.DataFrame) -> None:
    bread = get_product_history(history, "Markets / A", "Bread")
    summary = summarize_product_history(bread)
    assert summary["latest_price"] == 4.0
    assert summary["cheapest_price"] == 4.0
    assert summary["cheapest_date"] == pd.Timestamp("2026-01-03")
    assert summary["change_since_first_pct"] == pytest.approx(-20.0)


def test_summarize_product_history_zero_first_price() -> None:
    frame = make_history(
        [
            ("2026-01-01", "R", "p", "P", "C", 0.0),
            ("2026-01-02", "R", "p", "P", "C", 5.0),
        ]
    )
    assert summarize_product_history(frame)["change_since_first_pct"] == 0.0


# --- calculate_retailer_average_trends ------------------------------------


def test_retailer_average_trends_mean(history: pd.DataFrame) -> None:
    result = calculate_retailer_average_trends(history, ["Markets / A"], "Mean")
    assert list(result.columns) == ["date", "retailer", "price"]
    assert result["price"].tolist() == pytest.approx([15.0, 10.0, 9.5])  # (10+5+30)/3, (12+8)/2, (15+4)/2


def test_retailer_average_trends_median(history: pd.DataFrame) -> None:
    result = calculate_retailer_average_trends(history, ["Markets / A"], "Median")
    assert result["price"].tolist() == pytest.approx([10.0, 10.0, 9.5])


def test_retailer_average_trends_sorted_by_retailer_then_date(history: pd.DataFrame) -> None:
    result = calculate_retailer_average_trends(history, ["Markets / B", "Markets / A"], "Mean")
    assert result["retailer"].tolist() == ["Markets / A"] * 3 + ["Markets / B"] * 2
    assert result[result["retailer"] == "Markets / B"]["date"].is_monotonic_increasing


def test_retailer_average_trends_no_selection(history: pd.DataFrame) -> None:
    result = calculate_retailer_average_trends(history, ["Unknown"], "Mean")
    assert result.empty
    assert list(result.columns) == ["date", "retailer", "price"]


# --- calculate_price_movers -----------------------------------------------


def test_price_movers_empty(empty_history: pd.DataFrame) -> None:
    result = calculate_price_movers(empty_history, "All retailers", 5)
    assert all(frame.empty for frame in result.values())


def test_price_movers_excludes_single_observations(history: pd.DataFrame) -> None:
    stats = calculate_price_movers(history, "All retailers", 10)["stats"]
    assert "Eggs" not in stats["product_name"].tolist()
    assert sorted(stats["product_name"].tolist()) == ["Bread", "Cheese", "Milk"]


def test_price_movers_metrics(history: pd.DataFrame) -> None:
    stats = calculate_price_movers(history, "All retailers", 10)["stats"].set_index("product_name")
    milk, bread = stats.loc["Milk"], stats.loc["Bread"]
    assert milk["change_since_first_pct"] == pytest.approx(50.0)
    assert milk["drop_from_peak_pct"] == pytest.approx(0.0)
    assert bread["change_since_first_pct"] == pytest.approx(-20.0)
    assert bread["drop_from_peak_pct"] == pytest.approx(-50.0)
    assert bread["savings_vs_peak"] == pytest.approx(4.0)
    assert bread["observations"] == 3
    assert bread["first_seen"] == pd.Timestamp("2026-01-01")
    assert bread["last_seen"] == pd.Timestamp("2026-01-03")


def test_price_movers_ranking_and_limit(history: pd.DataFrame) -> None:
    result = calculate_price_movers(history, "All retailers", 1)
    assert result["biggest_drops"]["product_name"].tolist() == ["Bread"]
    assert result["biggest_gains"]["product_name"].tolist() == ["Milk"]


def test_price_movers_single_retailer_scope(history: pd.DataFrame) -> None:
    stats = calculate_price_movers(history, "Markets / B", 10)["stats"]
    assert stats["product_name"].tolist() == ["Cheese"]
    assert stats["change_since_first_pct"].iloc[0] == pytest.approx(0.0)


def test_price_movers_all_single_observations() -> None:
    frame = make_history([("2026-01-01", "R", "p", "P", "C", 1.0)])
    result = calculate_price_movers(frame, "All retailers", 5)
    assert all(df.empty for df in result.values())


def test_price_movers_independent_of_row_order(history: pd.DataFrame) -> None:
    reversed_history = history.iloc[::-1]
    stats = calculate_price_movers(reversed_history, "All retailers", 10)["stats"].set_index("product_name")
    assert stats.loc["Milk", "first_price"] == 10.0
    assert stats.loc["Milk", "latest_price"] == 15.0
    assert stats.loc["Milk", "change_since_first_pct"] == pytest.approx(50.0)
    assert stats.loc["Bread", "change_since_first_pct"] == pytest.approx(-20.0)


# --- coverage --------------------------------------------------------------


def test_coverage_summary(history: pd.DataFrame) -> None:
    skipped = pd.DataFrame({"path": ["bad.csv"]})
    assert calculate_coverage_summary(history, skipped) == {
        "retailer_count": 2,
        "product_count": 4,
        "observation_count": 9,
        "date_range": "2026-01-01 → 2026-01-03",
        "skipped_file_count": 1,
    }


def test_coverage_summary_empty(empty_history: pd.DataFrame) -> None:
    result = calculate_coverage_summary(empty_history, pd.DataFrame())
    assert result == {
        "retailer_count": 0,
        "product_count": 0,
        "observation_count": 0,
        "date_range": "-",
        "skipped_file_count": 0,
    }


def test_coverage_over_time(history: pd.DataFrame) -> None:
    result = calculate_coverage_over_time(history)
    assert list(result.columns) == ["date", "retailer", "tracked_products"]
    counts = {(row.date.strftime("%Y-%m-%d"), row.retailer): row.tracked_products for row in result.itertuples()}
    assert counts == {
        ("2026-01-01", "Markets / A"): 3,
        ("2026-01-01", "Markets / B"): 1,
        ("2026-01-02", "Markets / A"): 2,
        ("2026-01-03", "Markets / A"): 2,
        ("2026-01-03", "Markets / B"): 1,
    }


def test_coverage_over_time_empty(empty_history: pd.DataFrame) -> None:
    result = calculate_coverage_over_time(empty_history)
    assert result.empty
    assert list(result.columns) == ["date", "retailer", "tracked_products"]


def test_category_coverage_sorted_and_limited(history: pd.DataFrame) -> None:
    result = calculate_category_coverage(history)
    assert list(result.columns) == ["retailer", "category", "products"]
    assert result.iloc[0].to_dict() == {"retailer": "Markets / A", "category": "Dairy", "products": 2}
    assert result["products"].is_monotonic_decreasing
    assert len(calculate_category_coverage(history, limit=1)) == 1


def test_category_coverage_empty(empty_history: pd.DataFrame) -> None:
    result = calculate_category_coverage(empty_history)
    assert result.empty
    assert list(result.columns) == ["retailer", "category", "products"]
