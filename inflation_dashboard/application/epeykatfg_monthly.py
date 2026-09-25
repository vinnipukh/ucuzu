"""Load the externally generated EpeyKatfg monthly-inflation artifact.

The data repository produces this CSV. The web repository receives it through
``EPEYKATFG_MONTHLY_CSV`` or the local ``data/inflation`` mount; no data-repository
code is imported at runtime.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MONTHLY_CSV = PROJECT_ROOT / "data" / "inflation" / "EpeyKatfg" / "monthly_inflation.csv"


def get_monthly_inflation_path() -> Path:
    """Return the configured EpeyKatfg monthly inflation artifact path."""
    configured = os.environ.get("EPEYKATFG_MONTHLY_CSV")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_MONTHLY_CSV.resolve()

# Columns kept as strings; everything else is converted to float when parseable.
_STRING_COLUMNS = {"month", "prev_month", "groups"}


def load_monthly_inflation() -> tuple[list[dict[str, object]], list[str]]:
    """Return (rows, header). Each row is a JSON-safe dict (floats where numeric)."""
    monthly_csv = get_monthly_inflation_path()
    if not monthly_csv.exists():
        return [], []
    rows: list[dict[str, object]] = []
    with monthly_csv.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            return [], []
        for record in reader:
            if not record:
                continue
            row: dict[str, object] = {}
            for index, column in enumerate(header):
                if index >= len(record):
                    break
                value = record[index]
                if column not in _STRING_COLUMNS:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                row[column] = value
            rows.append(row)
    return rows, header
