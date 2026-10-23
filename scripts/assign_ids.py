#!/usr/bin/env python3
"""Make the database's provisional item and family IDs permanent in ``data/matching/ids.json``.

The build (``scripts/build_database.py``) gives catalog products and families that
have no ID in ``ids.json`` the next unused numbers, in key order
(``inflation_dashboard.domain.matching.assign_ids``). This script appends exactly
those IDs to ``ids.json``, so later builds keep them and existing links stay valid:

    uv run python scripts/build_database.py
    uv run python scripts/assign_ids.py

Then commit ``data/matching/ids.json``. Existing entries are never changed or
removed; a database built from a different ``ids.json`` is refused (rebuild first).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_database import DATA_DIR, IDS_FILE, read_ids, write_ids  # noqa: E402


def _new_ids(known: dict[str, int], next_id: int, rows: list[tuple[int, str]], what: str) -> dict[str, int]:
    """Database IDs missing from ``known``; raises ``SystemExit`` if the database disagrees with the file."""
    new = {}
    for value, key in rows:
        if key in known:
            if known[key] != value:
                raise SystemExit(f"{what} {key!r} is {value} in the database but {known[key]} in ids.json; rebuild first")
        elif value < next_id:
            raise SystemExit(f"{what} {key!r} has ID {value}, below the next free ID {next_id}; rebuild first")
        else:
            new[key] = value
    return new


def assign(db_path: Path, ids_path: Path) -> tuple[int, int]:
    """Append the database's new item and family IDs to ``ids_path``; return how many were added."""
    items, families, next_item, next_family = read_ids(ids_path)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        new_items = _new_ids(items, next_item, conn.execute("SELECT item_id, match_key FROM items").fetchall(), "item")
        new_families = _new_ids(
            families, next_family, conn.execute("SELECT family_id, family_key FROM families").fetchall(), "family"
        )
    finally:
        conn.close()
    if new_items or new_families:
        items.update(new_items)
        families.update(new_families)
        write_ids(
            ids_path,
            items,
            families,
            max(next_item, max(items.values(), default=0) + 1),
            max(next_family, max(families.values(), default=0) + 1),
        )
    return len(new_items), len(new_families)


def main() -> int:
    """CLI entry point: ``--db-path`` (default ``PRICES_DB_PATH`` or data/prices.db), ``--ids``."""
    parser = argparse.ArgumentParser(description="Append the database's new item/family IDs to data/matching/ids.json")
    parser.add_argument("--db-path", type=Path, default=Path(os.environ.get("PRICES_DB_PATH", DATA_DIR / "prices.db")))
    parser.add_argument("--ids", type=Path, default=DATA_DIR / IDS_FILE)
    args = parser.parse_args()
    added_items, added_families = assign(args.db_path.resolve(), args.ids.resolve())
    print(f"{args.ids}: {added_items:,} new item IDs, {added_families:,} new family IDs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
