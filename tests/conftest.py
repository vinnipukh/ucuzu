from __future__ import annotations

import pandas as pd
import pytest

from inflation_dashboard.domain.prices import HISTORY_COLUMNS


def make_history(rows: list[tuple]) -> pd.DataFrame:
    """Build a history frame from (date, retailer, product_id, product_name, category, price) tuples."""
    frame = pd.DataFrame(rows, columns=HISTORY_COLUMNS[:-1])
    frame["date"] = pd.to_datetime(frame["date"])
    frame["source_file"] = "fixture.csv"
    return frame[HISTORY_COLUMNS]


@pytest.fixture
def empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=HISTORY_COLUMNS)


@pytest.fixture
def history() -> pd.DataFrame:
    # Two retailers; milk rises 10 -> 15, bread peaks at 8 then falls to 4,
    # eggs is observed once, cheese is stable.
    return make_history(
        [
            ("2026-01-01", "Markets / A", "p1", "Milk", "Dairy", 10.0),
            ("2026-01-02", "Markets / A", "p1", "Milk", "Dairy", 12.0),
            ("2026-01-03", "Markets / A", "p1", "Milk", "Dairy", 15.0),
            ("2026-01-01", "Markets / A", "p2", "Bread", "Bakery", 5.0),
            ("2026-01-02", "Markets / A", "p2", "Bread", "Bakery", 8.0),
            ("2026-01-03", "Markets / A", "p2", "Bread", "Bakery", 4.0),
            ("2026-01-01", "Markets / A", "p3", "Eggs", "Dairy", 30.0),
            ("2026-01-01", "Markets / B", "p4", "Cheese", "Dairy", 100.0),
            ("2026-01-03", "Markets / B", "p4", "Cheese", "Dairy", 100.0),
        ]
    )
