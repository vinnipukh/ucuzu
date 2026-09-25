#!/usr/bin/env python3
"""Build the canonical read-optimized SQLite database from partitioned JSON."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_obs_retailer_date_price ON price_observations(retailer, date, price)",
    "CREATE INDEX IF NOT EXISTS idx_obs_ret_prod_date_price ON price_observations(retailer, product_id, date, price)",
    "CREATE INDEX IF NOT EXISTS idx_obs_retailer_name_date ON price_observations(retailer, product_name, date)",
    "CREATE INDEX IF NOT EXISTS idx_obs_retailer_date ON price_observations(retailer, date)",
    "CREATE INDEX IF NOT EXISTS idx_obs_date_retailer ON price_observations(date, retailer)",
    "CREATE INDEX IF NOT EXISTS idx_obs_retailer_product ON price_observations(retailer, product_id)",
    "CREATE INDEX IF NOT EXISTS idx_product_ret_cat_prod ON product_prices(retailer, category, product_id)",
    "CREATE INDEX IF NOT EXISTS idx_product_movers_covering ON product_prices(retailer, observations_count, max_price, latest_price, min_price, product_name, category, product_id)",
    "CREATE INDEX IF NOT EXISTS idx_product_global_movers_covering ON product_prices(observations_count, max_price, latest_price, min_price, retailer, product_name, category, product_id)",
    "CREATE INDEX IF NOT EXISTS idx_product_retailer_dates ON product_prices(retailer, first_date, last_date)",
    "CREATE INDEX IF NOT EXISTS idx_product_retailer_obs ON product_prices(retailer, observations_count)",
    "CREATE INDEX IF NOT EXISTS idx_product_name ON product_prices(product_name)",
    "CREATE INDEX IF NOT EXISTS idx_product_retailer_category ON product_prices(retailer, category)",
    "CREATE INDEX IF NOT EXISTS idx_product_retailer ON product_prices(retailer)",
    "CREATE INDEX IF NOT EXISTS idx_ingested_retailer_date ON ingested_files(retailer, date)",
)


def init_db(conn: sqlite3.Connection) -> None:
    """Create the canonical API-serving schema."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA cache_size = -128000")
    conn.execute("PRAGMA mmap_size = 1073741824")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS product_prices (
            product_id TEXT NOT NULL,
            retailer TEXT NOT NULL,
            product_name TEXT,
            category TEXT,
            first_date TEXT,
            last_date TEXT,
            latest_price REAL,
            min_price REAL,
            max_price REAL,
            observations_count INTEGER,
            price_history JSON,
            PRIMARY KEY (retailer, product_id)
        );

        CREATE TABLE IF NOT EXISTS price_observations (
            date TEXT NOT NULL,
            retailer TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT,
            category TEXT,
            price REAL NOT NULL,
            source_file TEXT,
            PRIMARY KEY (date, retailer, product_id)
        );

        CREATE TABLE IF NOT EXISTS ingested_files (
            file_path TEXT PRIMARY KEY,
            retailer TEXT NOT NULL,
            date TEXT,
            file_size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            rows_ingested INTEGER NOT NULL,
            ingested_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create the indexes used by API aggregates and product lookup routes."""
    print("Creating indexes...")
    for statement in INDEX_STATEMENTS:
        conn.execute(statement)
    conn.commit()


def retailer_from_stem(stem: str) -> str:
    """Convert a partition filename stem into the API's retailer label."""
    retailer = stem.replace("_", " / ")
    aliases = {
        "Health / Diagnostic / Surgical / Services": "Health / Diagnostic&Surgical Services",
    }
    return aliases.get(retailer, retailer)


def json_to_sqlite(json_dir: Path, db_path: Path, include_observations: bool = True) -> None:
    print("=== Building SQLite Database from JSON ===")
    print(f"Source JSON Directory: {json_dir}")
    print(f"Target SQLite Database: {db_path}")

    if not json_dir.is_dir():
        raise SystemExit(f"JSON directory does not exist: {json_dir}")

    json_files = sorted(json_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in {json_dir}")
    if not include_observations:
        print("WARNING: --no-obs produces a product-only database; the full Falcon API requires price_observations.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()

    started = time.perf_counter()
    total_products = 0
    total_observations = 0
    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)
        ingested_at = datetime.now(timezone.utc).isoformat()

        for json_file in json_files:
            file_started = time.perf_counter()
            retailer = retailer_from_stem(json_file.stem)
            with json_file.open(encoding="utf-8") as handle:
                payload = json.load(handle)

            product_rows: list[tuple[object, ...]] = []
            observation_rows: list[tuple[object, ...]] = []

            for raw_product_id, product in payload.items():
                prices = product.get("prices") or {}
                if not isinstance(prices, dict):
                    continue
                ordered_dates = sorted(prices)
                first_date = ordered_dates[0] if ordered_dates else None
                last_date = ordered_dates[-1] if ordered_dates else None
                numeric_prices = [float(value) for value in prices.values()]
                latest_price = float(prices[last_date]) if last_date else product.get("latest_price")
                min_price = min(numeric_prices) if numeric_prices else product.get("min_price")
                max_price = max(numeric_prices) if numeric_prices else product.get("max_price")
                product_id = str(raw_product_id)
                product_name = product.get("name")
                category = product.get("category")

                product_rows.append(
                    (
                        product_id,
                        retailer,
                        product_name,
                        category,
                        first_date,
                        last_date,
                        latest_price,
                        min_price,
                        max_price,
                        len(prices),
                        json.dumps(prices, ensure_ascii=False, separators=(",", ":")),
                    )
                )

                if include_observations:
                    observation_rows.extend(
                        (
                            date_value,
                            retailer,
                            product_id,
                            product_name,
                            category,
                            float(price_value),
                            json_file.name,
                        )
                        for date_value, price_value in prices.items()
                    )

            conn.executemany(
                """
                INSERT OR REPLACE INTO product_prices (
                    product_id, retailer, product_name, category, first_date,
                    last_date, latest_price, min_price, max_price,
                    observations_count, price_history
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                product_rows,
            )
            if observation_rows:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO price_observations (
                        date, retailer, product_id, product_name, category, price, source_file
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    observation_rows,
                )

            stat = json_file.stat()
            if include_observations:
                ledger_rows = [
                    (
                        f"{json_file.name}#{date_value}",
                        retailer,
                        date_value,
                        stat.st_size,
                        stat.st_mtime,
                        row_count,
                        ingested_at,
                    )
                    for date_value, row_count in sorted(Counter(row[0] for row in observation_rows).items())
                ]
            else:
                partition_dates = sorted({row[4] for row in product_rows if row[4]})
                ledger_rows = [
                    (
                        f"{json_file.name}#{date_value}",
                        retailer,
                        date_value,
                        stat.st_size,
                        stat.st_mtime,
                        len(product_rows),
                        ingested_at,
                    )
                    for date_value in partition_dates
                ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO ingested_files (
                    file_path, retailer, date, file_size, mtime, rows_ingested, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ledger_rows,
            )
            conn.commit()
            total_products += len(product_rows)
            total_observations += len(observation_rows)
            elapsed = time.perf_counter() - file_started
            print(
                f"  Loaded {json_file.name}: {len(product_rows):,} products, "
                f"{len(observation_rows):,} observations ({elapsed:.2f}s)"
            )

        create_indexes(conn)
        conn.execute("ANALYZE")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    elapsed = time.perf_counter() - started
    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print("=== Build Complete ===")
    print(f"Partitions: {len(json_files)}")
    print(f"Total Products: {total_products:,}")
    print(f"Total Price Observations: {total_observations:,}")
    print(f"SQLite DB: {db_path} ({db_size_mb:.2f} MB)")
    print(f"Elapsed Time: {elapsed:.2f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SQLite DB from partitioned JSON price history")
    parser.add_argument("--json-dir", default="data/prices_json", help="Path to partitioned JSON directory")
    parser.add_argument("--db-path", default="data/prices.db", help="Path to output SQLite database")
    parser.add_argument("--no-obs", action="store_true", help="Omit observations (not compatible with the full API)")
    args = parser.parse_args()

    json_to_sqlite(
        Path(args.json_dir).expanduser().resolve(),
        Path(args.db_path).expanduser().resolve(),
        include_observations=not args.no_obs,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
