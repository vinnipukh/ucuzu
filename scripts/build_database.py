#!/usr/bin/env python3
"""Build the serving SQLite database from the committed ``data/`` tree.

This is the one command that turns committed scraper output into
``data/prices.db`` (the database itself is never committed):

    uv run python scripts/build_database.py

Steps:
1. Rebuild any file that was committed as ``.partNNN`` chunks (scripts/data_files.py).
2. Ingest every dated CSV under ``data/raw`` (TÜİK-grouped scraper output) into
   ``price_observations``, labelling retailers the way the API/UI expects
   (``01_Food/Gurmar`` -> ``Markets / Gurmar``).
3. Ingest ``data/prices_json`` partitions only for retailers that have no raw CSVs.
4. Rebuild ``product_prices``, create the API indexes and atomically replace the target.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
for entry in (REPO_ROOT, Path(__file__).resolve().parent):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import data_files  # noqa: E402
from build_sqlite_from_json import INDEX_STATEMENTS, init_db, retailer_from_stem  # noqa: E402

from inflation_dashboard.domain.prices import PRICE_COLUMNS, build_product_frame  # noqa: E402

DATA_DIR = REPO_ROOT / "data"

# TÜİK COICOP folders whose stores map onto the API's existing retailer groups.
GROUP_LABELS = {
    "01_Food": "Markets",
    "03_Clothing": "ClothingStores",
    "04_Housing": "HousesRent",
    "06_Health": "Health",
}
# Folders that are themselves a retailer group (e.g. 05_Furnishings/HomeGoods/Ikea).
NESTED_GROUPS = {"ConstructionSuppliesMarkets", "HomeGoods", "Cosmetics"}
TUIK_FOLDER = re.compile(r"^\d{2}_(?P<name>.+)$")

DATE_PATTERNS = (
    (re.compile(r"(?<!\d)(20\d{2})[-_.](\d{2})[-_.](\d{2})(?!\d)"), (1, 2, 3)),
    (re.compile(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](20\d{2})(?!\d)"), (3, 2, 1)),
    (re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"), (1, 2, 3)),
)


def parse_file_date(name: str) -> str | None:
    """Return the ISO date embedded in a scraper file name, if any."""
    for pattern, (y, m, d) in DATE_PATTERNS:
        for match in pattern.finditer(name):
            try:
                return date(int(match[y]), int(match[m]), int(match[d])).isoformat()
            except ValueError:
                continue
    return None


def raw_retailer_label(relative_dirs: tuple[str, ...]) -> str | None:
    """Map a CSV's folder path under data/raw to the API retailer label."""
    if not relative_dirs:
        return None
    head, rest = relative_dirs[0], relative_dirs[1:]
    match = TUIK_FOLDER.match(head)
    if not match:
        return " / ".join(relative_dirs)
    if not rest:
        return GROUP_LABELS.get(head, match["name"])
    if rest[0] in NESTED_GROUPS and len(rest) > 1:
        return f"{rest[0]} / {rest[1]}"
    group = GROUP_LABELS.get(head, match["name"].replace("_", " "))
    # Housing groups regions into sub-folders; the leaf city is the series.
    store = rest[-1] if head == "04_Housing" else rest[0]
    return f"{group} / {store}"


def _read_csv(path: Path) -> pd.DataFrame:
    with path.open("rb") as handle:
        first_line = handle.readline().decode("utf-8", errors="replace")
    sep = max((";", ",", "\t"), key=first_line.count)
    for encoding in ("utf-8-sig", "cp1254"):
        try:
            return pd.read_csv(path, sep=sep, encoding=encoding, on_bad_lines="skip", low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError("undecodable")


def _ingest_file(args: tuple[str, str, str, str]) -> tuple[str, list[tuple], str | None]:
    path_str, rel, retailer, date_str = args
    try:
        frame = _read_csv(Path(path_str))
    except Exception as exc:  # noqa: BLE001 - one bad scrape must not stop the build
        return rel, [], f"unreadable ({type(exc).__name__})"
    price_column = next((column for column in PRICE_COLUMNS if column in frame.columns), None)
    if frame.empty or price_column is None:
        return rel, [], "no price column"
    try:
        products = build_product_frame(frame, retailer, price_column, pd.Timestamp(date_str), rel)
    except Exception as exc:  # noqa: BLE001
        return rel, [], f"unparseable ({type(exc).__name__})"
    rows = [
        (
            date_str,
            retailer,
            str(row.product_id).strip(),
            str(row.product_name).strip(),
            str(row.category or "Uncategorized").strip(),
            float(row.price),
            rel,
        )
        for row in products.itertuples(index=False)
    ]
    return rel, rows, None if rows else "no usable rows"


def discover_raw_csvs(raw_dir: Path) -> tuple[list[tuple[str, str, str, str]], Counter]:
    jobs, skipped = [], Counter()
    for path in sorted(raw_dir.rglob("*.csv")):
        rel_parts = path.relative_to(raw_dir).parts
        retailer = raw_retailer_label(rel_parts[:-1])
        date_str = parse_file_date(path.name)
        if retailer is None or date_str is None:
            skipped["undated or unlabelled"] += 1
            continue
        jobs.append((str(path), path.relative_to(raw_dir.parent).as_posix(), retailer, date_str))
    return jobs, skipped


def ingest_raw(conn: sqlite3.Connection, raw_dir: Path, workers: int) -> set[str]:
    jobs, skipped = discover_raw_csvs(raw_dir)
    print(f"Raw CSVs: {len(jobs)} dated files to ingest from {raw_dir}")
    by_rel = {job[1]: job for job in jobs}
    ingested_at = datetime.now(timezone.utc).isoformat()
    retailers: set[str] = set()
    started = time.perf_counter()
    total_rows = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for done, (rel, rows, problem) in enumerate(pool.map(_ingest_file, jobs, chunksize=8), 1):
            if problem:
                skipped[problem] += 1
                continue
            path_str, _, retailer, date_str = by_rel[rel]
            stat = Path(path_str).stat()
            conn.executemany("INSERT OR REPLACE INTO price_observations VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
            conn.execute(
                "INSERT OR REPLACE INTO ingested_files VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rel, retailer, date_str, stat.st_size, stat.st_mtime, len(rows), ingested_at),
            )
            retailers.add(retailer)
            total_rows += len(rows)
            if done % 500 == 0:
                conn.commit()
                print(f"  [{done}/{len(jobs)}] {total_rows:,} rows, {time.perf_counter() - started:.0f}s")
    conn.commit()
    print(f"Raw CSVs: {total_rows:,} rows from {len(retailers)} retailers in {time.perf_counter() - started:.0f}s")
    for reason, count in sorted(skipped.items()):
        print(f"  skipped {count} files: {reason}")
    return retailers


def ingest_json_fallback(conn: sqlite3.Connection, json_dir: Path, covered: set[str]) -> None:
    if not json_dir.is_dir():
        return
    ingested_at = datetime.now(timezone.utc).isoformat()
    for json_file in sorted(json_dir.glob("*.json")):
        retailer = retailer_from_stem(json_file.stem)
        if retailer in covered:
            continue
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        rel = json_file.relative_to(json_dir.parent).as_posix()
        rows = [
            (str(day), retailer, str(product_id), product.get("name") or str(product_id),
             product.get("category") or "Uncategorized", float(price), rel)
            for product_id, product in payload.items()
            for day, price in (product.get("prices") or {}).items()
            if price is not None
        ]
        conn.executemany("INSERT OR REPLACE INTO price_observations VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        # One synthetic ledger row per date keeps the API's newest-N-files selection meaningful.
        stat = json_file.stat()
        conn.executemany(
            "INSERT OR REPLACE INTO ingested_files VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (f"{json_file.name}#{day}", retailer, day, stat.st_size, stat.st_mtime, count, ingested_at)
                for day, count in sorted(Counter(row[0] for row in rows).items())
            ],
        )
        print(f"JSON fallback: {retailer} ({len(rows):,} rows from {json_file.name})")
    conn.commit()


def rebuild_product_prices(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_obs_ret_prod_date_price
            ON price_observations(retailer, product_id, date, price);
        DROP TABLE IF EXISTS temp.latest;
        CREATE TEMP TABLE latest AS
            SELECT retailer, product_id, product_name, category, price
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY retailer, product_id ORDER BY date DESC) AS rn
                FROM price_observations
            )
            WHERE rn = 1;
        DELETE FROM product_prices;
        INSERT INTO product_prices
        SELECT o.product_id, o.retailer, l.product_name, l.category,
               min(o.date), max(o.date), l.price, min(o.price), max(o.price), count(*),
               json_group_object(o.date, o.price)
        FROM (SELECT * FROM price_observations ORDER BY retailer, product_id, date) AS o
        JOIN temp.latest AS l USING (retailer, product_id)
        GROUP BY o.retailer, o.product_id;
        DROP TABLE temp.latest;
        """
    )
    conn.commit()


def build(data_dir: Path, db_path: Path, workers: int) -> None:
    started = time.perf_counter()
    data_files.join(data_dir)
    building = db_path.with_name(db_path.name + ".building")
    for suffix in ("", "-wal", "-shm"):
        Path(f"{building}{suffix}").unlink(missing_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(building)
    try:
        init_db(conn)
        conn.execute("PRAGMA synchronous = OFF")
        covered = ingest_raw(conn, data_dir / "raw", workers)
        ingest_json_fallback(conn, data_dir / "prices_json", covered)
        print("Rebuilding product_prices...")
        rebuild_product_prices(conn)
        print("Creating API indexes...")
        for statement in INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute("ANALYZE")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        products = conn.execute("SELECT count(*) FROM product_prices").fetchone()[0]
        observations = conn.execute("SELECT count(*) FROM price_observations").fetchone()[0]
        retailers = conn.execute("SELECT count(DISTINCT retailer) FROM product_prices").fetchone()[0]
    finally:
        conn.close()

    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    os.replace(building, db_path)
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(
        f"\nBuilt {db_path} ({size_mb:.0f} MB): {retailers} retailers, {products:,} products, "
        f"{observations:,} observations in {time.perf_counter() - started:.0f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/prices.db from committed scraper data")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--db-path", type=Path, default=Path(os.environ.get("PRICES_DB_PATH", DATA_DIR / "prices.db")))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    build(args.data_dir.resolve(), args.db_path.resolve(), args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
