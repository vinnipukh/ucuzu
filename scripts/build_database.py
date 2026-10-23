#!/usr/bin/env python3
"""Build the serving SQLite database from the committed ``data/`` tree.

This is the one command that turns committed scraper output into
``data/prices.db`` (the database itself is never committed):

    uv run python scripts/build_database.py

Steps:
1. Rebuild any file that was committed as ``.partNNN`` chunks (scripts/data_files.py).
2. Ingest every dated CSV under ``data/raw`` (TÜİK-grouped scraper output),
   labelling retailers the way the API/UI expects (``01_Food/Gurmar`` -> ``Markets / Gurmar``).
3. Ingest ``data/prices_json`` partitions only for retailers that have no raw CSVs.
4. Write the normalized schema (see SCHEMA), summarize products, compute unit
   prices from the titles (domain.product_attributes) and atomically replace the
   target.

Storage is normalized: each retailer, category, source file and product is stored
once and ``observations`` holds only integer keys, the date and the price,
clustered by (product_key, date). Read-only views named ``price_observations``,
``product_prices`` and ``ingested_files`` expose the historical row shapes the API
queries.
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

from inflation_dashboard.domain.catalog import name_key  # noqa: E402
from inflation_dashboard.domain.prices import (  # noqa: E402
    CATEGORY_COLUMNS,
    DETAIL_COLUMNS,
    ID_COLUMNS,
    NAME_COLUMNS,
    PRICE_COLUMNS,
    build_product_frame,
    header_key,
)
from inflation_dashboard.domain.product_attributes import parse, unit_price  # noqa: E402

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

# Header spellings used by individual scrapers, in priority order, keyed by their
# normalized form (casefolded; spaces, "_", "-" and dotted-İ marks removed). They are
# renamed to the domain's canonical columns only when no canonical column exists.
NAME_ALIASES = ("productname", "name", "urunadi", "ürünadı", "urunismi", "isim", "ad", "urun", "title")
PRICE_ALIASES = (
    "price", "fiyat", "fiyatfloat", "pricetl", "price(tl)", "saleprice", "currentprice",
    "productcost", "normalprice", "regularprice",
)
# Category names only: ``category_number`` / ``sub_category_number`` hold TÜİK codes
# (``05``, ``0511116``), not shop categories, and are deliberately not aliased.
CATEGORY_ALIASES = ("fullcategory", "categorypath", "anakategori", "kategori", "subcategory", "topcategory")
ID_ALIASES = ("urunid", "productcode", "sku", "productid")

DATE_PATTERNS = (
    (re.compile(r"(?<!\d)(20\d{2})[-_.](\d{2})[-_.](\d{2})(?!\d)"), (1, 2, 3)),
    (re.compile(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](20\d{2})(?!\d)"), (3, 2, 1)),
    (re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"), (1, 2, 3)),
)
# Some upstream scrapers name files by month and day only (``products10-19.csv``,
# ``Clothes3-10.csv``). Upstream started on 2026-02-23 (InflationResearchStudy's creation
# date) and no such file was committed before its name date read as 2026, so a
# month-day is read as its first occurrence on or after SCRAPE_START. That is
# unambiguous only for scrapes before 2027-02-23; see docs/DATABASE.md.
MONTH_DAY_PATTERN = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})$")
SCRAPE_START = date(2026, 2, 23)

UNCATEGORIZED = "Uncategorized"
# Products last seen longer ago than this (before the newest date in the database)
# are not current, so retailers that stopped being scraped drop out of the catalog.
CURRENT_WINDOW_DAYS = 45

SCHEMA = """
CREATE TABLE retailers (
    retailer_key INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE categories (
    category_key INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
-- One row per ingested source file (JSON partitions get one synthetic row per date).
CREATE TABLE sources (
    source_key INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    retailer_key INTEGER NOT NULL REFERENCES retailers,
    date TEXT,
    file_size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    rows_ingested INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
);
-- One row per (retailer, product); name and category are the latest observed values.
-- name_key (domain.catalog.name_key) matches the same item across retailers;
-- previous_price/price_since describe the latest price change and is_current marks
-- products seen within 7 days of their retailer's newest date and within
-- CURRENT_WINDOW_DAYS of the newest date in the database. is_store_latest marks
-- products whose last_date is the newest among the retailer's products with the
-- same name_key (the store's latest prices for that item).
-- brand, barcode, image_url and product_url are the newest non-empty values the
-- scraper sent; regular_price (the undiscounted price) only when it was sent on
-- last_date. unit_price is latest_price per unit_price_unit (ml, g, adet, yikama,
-- m or m2) parsed from the title; NULL when the title has no contents size.
CREATE TABLE products (
    product_key INTEGER PRIMARY KEY,
    retailer_key INTEGER NOT NULL REFERENCES retailers,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    name_key TEXT NOT NULL,
    category_key INTEGER NOT NULL REFERENCES categories,
    first_date TEXT,
    last_date TEXT,
    latest_price REAL,
    min_price REAL,
    max_price REAL,
    observations_count INTEGER,
    previous_price REAL,
    price_since TEXT,
    is_current INTEGER NOT NULL DEFAULT 0,
    is_store_latest INTEGER NOT NULL DEFAULT 0,
    brand TEXT,
    barcode TEXT,
    image_url TEXT,
    product_url TEXT,
    regular_price REAL,
    unit_price REAL,
    unit_price_unit TEXT,
    UNIQUE (retailer_key, product_id)
);
-- One row per product per day, clustered so a product's history is one range read.
CREATE TABLE observations (
    product_key INTEGER NOT NULL,
    date TEXT NOT NULL,
    price REAL NOT NULL,
    category_key INTEGER NOT NULL,
    source_key INTEGER NOT NULL,
    PRIMARY KEY (product_key, date)
) WITHOUT ROWID;
"""

INDEXES = """
CREATE INDEX idx_products_retailer_name ON products(retailer_key, product_name);
CREATE INDEX idx_products_name ON products(product_name);
CREATE INDEX idx_products_product_id ON products(product_id);
CREATE INDEX idx_products_name_key ON products(name_key);
CREATE INDEX idx_sources_retailer_date ON sources(retailer_key, date);
"""

# Read-only views with the historical row shapes queried by the API adapters.
VIEWS = """
CREATE VIEW price_observations AS
SELECT o.date, r.name AS retailer, p.product_id, p.product_name, c.name AS category, o.price,
       s.file_path AS source_file
FROM observations AS o
JOIN products AS p ON p.product_key = o.product_key
JOIN retailers AS r ON r.retailer_key = p.retailer_key
JOIN categories AS c ON c.category_key = o.category_key
JOIN sources AS s ON s.source_key = o.source_key;

CREATE VIEW product_prices AS
SELECT p.product_id, r.name AS retailer, p.product_name, c.name AS category,
       p.first_date, p.last_date, p.latest_price, p.min_price, p.max_price, p.observations_count,
       (SELECT json_group_object(o.date, o.price) FROM observations AS o
        WHERE o.product_key = p.product_key) AS price_history
FROM products AS p
JOIN retailers AS r ON r.retailer_key = p.retailer_key
JOIN categories AS c ON c.category_key = p.category_key;

CREATE VIEW ingested_files AS
SELECT s.file_path, r.name AS retailer, s.date, s.file_size, s.mtime, s.rows_ingested, s.ingested_at
FROM sources AS s
JOIN retailers AS r ON r.retailer_key = s.retailer_key;
"""


def parse_file_date(name: str) -> str | None:
    """Return the ISO date embedded in a scraper file name, if any.

    Full dates (``DATE_PATTERNS``) win; otherwise a ``<month>-<day>`` stem suffix is
    dated in the year that puts it within a year from ``SCRAPE_START``.
    """
    for pattern, (y, m, d) in DATE_PATTERNS:
        for match in pattern.finditer(name):
            try:
                return date(int(match[y]), int(match[m]), int(match[d])).isoformat()
            except ValueError:
                continue
    match = MONTH_DAY_PATTERN.search(Path(name).stem)
    if match:
        for year in (SCRAPE_START.year, SCRAPE_START.year + 1):
            try:
                day = date(year, int(match[1]), int(match[2]))
            except ValueError:
                continue
            if SCRAPE_START <= day < SCRAPE_START.replace(year=SCRAPE_START.year + 1):
                return day.isoformat()
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


# Partition stems whose plain mapping differs from the retailer label (stem mapping -> label).
STEM_ALIASES = {
    "Health / Diagnostic_Surgical_Services": "Health / Diagnostic&Surgical Services",
}


def retailer_from_stem(stem: str) -> str:
    """Convert a prices_json partition stem into the API's retailer label.

    The first ``_`` separates group and store (``Markets_Gurmar`` -> ``Markets /
    Gurmar``); later underscores belong to the store (``Education_Open_Education``
    -> ``Education / Open_Education``). ``retailer_stem`` is the inverse.
    """
    group, sep, store = stem.partition("_")
    retailer = f"{group} / {store}" if sep else stem
    return STEM_ALIASES.get(retailer, retailer)


def retailer_stem(retailer: str) -> str:
    """The prices_json partition stem for a retailer label (inverse of ``retailer_from_stem``).

    Raises ``ValueError`` for labels that cannot round-trip: more than one `` / ``,
    an ``_`` in the group, or a character Windows forbids in file names.
    """
    aliased = next((plain for plain, label in STEM_ALIASES.items() if label == retailer), retailer)
    group, sep, store = aliased.partition(" / ")
    stem = f"{group}_{store}" if sep else aliased
    if " / " in store or "_" in group or re.search(r'[\\/:*?"<>|]', stem) or retailer_from_stem(stem) != retailer:
        raise ValueError(f"Retailer label has no prices_json file name: {retailer!r}")
    return stem


_header_key = header_key


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename scraper-specific name/price/category/id headers to the domain's canonical columns."""
    by_key: dict[str, object] = {}
    for column in frame.columns:
        by_key.setdefault(_header_key(column), column)
    renames = {}
    for canonical, known, aliases in (
        ("name", NAME_COLUMNS, NAME_ALIASES),
        ("price", PRICE_COLUMNS, PRICE_ALIASES),
        ("category", CATEGORY_COLUMNS, CATEGORY_ALIASES),
        ("product_id", ID_COLUMNS, ID_ALIASES),
    ):
        if any(column in frame.columns for column in known):
            continue
        source = next((by_key[alias] for alias in aliases if alias in by_key), None)
        if source is not None:
            renames[source] = canonical
    return frame.rename(columns=renames) if renames else frame


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a scraped CSV with the most frequent of ``;``, ``,`` or tab as delimiter.

    Tries UTF-8 (BOM-aware) then cp1254 and skips malformed lines; raises
    ``ValueError("undecodable")`` when neither encoding works.
    """
    with path.open("rb") as handle:
        first_line = handle.readline().decode("utf-8", errors="replace")
    sep = max((";", ",", "\t"), key=first_line.count)
    for encoding in ("utf-8-sig", "cp1254"):
        try:
            return pd.read_csv(path, sep=sep, encoding=encoding, on_bad_lines="skip", low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError("undecodable")


def _detail(value: object) -> object:
    return None if value is None or pd.isna(value) else value


def _ingest_file(args: tuple[str, str, str, str]) -> tuple[str, list[tuple], str | None]:
    """Parse one CSV into ``(product_id, product_name, category, price, *details)`` rows (worker process).

    ``details`` are the ``DETAIL_COLUMNS`` values, ``None`` where missing.
    """
    path_str, rel, retailer, date_str = args
    try:
        frame = normalize_columns(_read_csv(Path(path_str)))
    except Exception as exc:  # noqa: BLE001 - one bad scrape must not stop the build
        return rel, [], f"unreadable ({type(exc).__name__})"
    if frame.empty:
        return rel, [], "empty (header only)"
    price_column = next((column for column in PRICE_COLUMNS if column in frame.columns), None)
    if price_column is None:
        return rel, [], "no price column"
    try:
        products = build_product_frame(frame, retailer, price_column, pd.Timestamp(date_str), rel)
    except Exception as exc:  # noqa: BLE001
        return rel, [], f"unparseable ({type(exc).__name__})"
    rows = [
        (
            str(row.product_id).strip(),
            str(row.product_name).strip(),
            str(row.category or UNCATEGORIZED).strip(),
            float(row.price),
            *(_detail(getattr(row, column)) for column in DETAIL_COLUMNS),
        )
        for row in products.itertuples(index=False)
    ]
    return rel, rows, None if rows else "no usable rows"


def discover_raw_csvs(raw_dir: Path) -> tuple[list[tuple[str, str, str, str]], Counter]:
    """List ingestible CSVs under ``raw_dir`` as worker jobs.

    Returns ``(jobs, skipped)``: each job is ``(absolute path, path relative to data/,
    retailer label, ISO date)``; files without a date or retailer label are counted
    in ``skipped`` under ``"undated or unlabelled"``.
    """
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


class Loader:
    """Assigns integer keys and streams observations into an append-only staging table.

    Observations are staged in arrival order; ``finish`` keeps the last row per
    (product, date), matching INSERT OR REPLACE semantics, and writes them
    clustered by (product_key, date).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.retailers: dict[str, int] = {}
        self.categories: dict[str, int] = {}
        # (retailer_key, product_id) -> [product_key, latest_date, product_name, category_key]
        self.products: dict[tuple[int, str], list] = {}
        # product_key -> {detail: (date, value)}, the newest non-empty value per detail
        self.details: dict[int, dict[str, tuple[str, object]]] = {}
        self.ingested_at = datetime.now(timezone.utc).isoformat()
        self.staged_rows = 0

    def _key(self, table: dict[str, int], name: str) -> int:
        key = table.get(name)
        if key is None:
            key = table[name] = len(table) + 1
        return key

    def add(self, file_path: str, retailer: str, date_str: str, size: int, mtime: float, rows: list[tuple]) -> None:
        """Register one source file and stage its rows as observations.

        Assigns retailer, category, source and product keys; a product's name and
        category follow its latest-dated row. ``rows`` are ``(product_id, product_name,
        category, price, *details)`` tuples; ``details`` (``DETAIL_COLUMNS``, optional)
        keep their newest non-empty value per product.
        """
        retailer_key = self._key(self.retailers, retailer)
        cursor = self.conn.execute(
            "INSERT INTO sources (file_path, retailer_key, date, file_size, mtime, rows_ingested, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_path, retailer_key, date_str, size, mtime, len(rows), self.ingested_at),
        )
        source_key = cursor.lastrowid
        staged = []
        for product_id, product_name, category, price, *details in rows:
            category_key = self._key(self.categories, category)
            entry = self.products.get((retailer_key, product_id))
            if entry is None:
                entry = self.products[(retailer_key, product_id)] = [len(self.products) + 1, date_str, product_name, category_key]
            elif date_str >= entry[1]:
                entry[1], entry[2], entry[3] = date_str, product_name, category_key
            staged.append((entry[0], date_str, price, category_key, source_key))
            if any(value is not None for value in details):
                known = self.details.setdefault(entry[0], {})
                for column, value in zip(DETAIL_COLUMNS, details):
                    if value is not None and (column not in known or date_str >= known[column][0]):
                        known[column] = (date_str, value)
        self.conn.executemany("INSERT INTO staging.obs VALUES (?, ?, ?, ?, ?)", staged)
        self.staged_rows += len(staged)

    def _detail_values(self, product_key: int, latest_date: str) -> tuple:
        """A product's ``DETAIL_COLUMNS`` values; the regular price only if sent on its latest date."""
        known = self.details.get(product_key, {})
        values = []
        for column in DETAIL_COLUMNS:
            date_str, value = known.get(column, (None, None))
            values.append(None if column == "regular_price" and date_str != latest_date else value)
        return tuple(values)

    def finish(self, workers: int = 1) -> None:
        """Write the key tables, deduplicated observations and product summaries.

        Inserts retailers, categories and products (with their details), copies the
        staged rows into ``observations`` keeping the last staged row per (product,
        date), then fills each product's first/last date, min/max price, observation
        count, latest price, latest price change (``previous_price``, ``price_since``),
        ``is_current``, ``is_store_latest`` and unit price (``write_unit_prices``).
        """
        conn = self.conn
        conn.executemany("INSERT INTO retailers VALUES (?, ?)", [(k, n) for n, k in self.retailers.items()])
        conn.executemany("INSERT INTO categories VALUES (?, ?)", [(k, n) for n, k in self.categories.items()])
        columns = ", ".join(DETAIL_COLUMNS)
        conn.executemany(
            f"INSERT INTO products (product_key, retailer_key, product_id, product_name, name_key, category_key, {columns}) "
            f"VALUES (?, ?, ?, ?, ?, ?{', ?' * len(DETAIL_COLUMNS)})",
            [
                (e[0], rk, pid, e[2], name_key(e[2]), e[3], *self._detail_values(e[0], e[1]))
                for (rk, pid), e in self.products.items()
            ],
        )
        conn.commit()
        print(f"Writing observations ({self.staged_rows:,} staged rows, last row per product/day wins)...")
        conn.execute(
            """
            INSERT INTO observations (product_key, date, price, category_key, source_key)
            SELECT product_key, date, price, category_key, source_key
            FROM (
                SELECT *, row_number() OVER (PARTITION BY product_key, date ORDER BY rowid DESC) AS rn
                FROM staging.obs
            )
            WHERE rn = 1
            ORDER BY product_key, date
            """
        )
        conn.commit()
        print("Summarizing products...")
        conn.execute(
            """
            UPDATE products SET
                first_date = agg.first_date, last_date = agg.last_date,
                min_price = agg.min_price, max_price = agg.max_price,
                observations_count = agg.n
            FROM (
                SELECT product_key, min(date) AS first_date, max(date) AS last_date,
                       min(price) AS min_price, max(price) AS max_price, count(*) AS n
                FROM observations GROUP BY product_key
            ) AS agg
            WHERE products.product_key = agg.product_key
            """
        )
        # SQLite returns the bare column from the row holding max(date).
        conn.execute(
            """
            UPDATE products SET latest_price = latest.price
            FROM (SELECT product_key, max(date), price FROM observations GROUP BY product_key) AS latest
            WHERE products.product_key = latest.product_key
            """
        )
        conn.commit()
        print("Computing price changes...")
        # previous_price is the price on the newest day that differs from latest_price;
        # price_since is the first day of the current price.
        conn.execute(
            """
            UPDATE products SET previous_price = prev.price, price_since = prev.since
            FROM (
                SELECT ch.product_key, o.price,
                       (SELECT min(o2.date) FROM observations AS o2
                        WHERE o2.product_key = ch.product_key AND o2.date > ch.changed) AS since
                FROM (
                    SELECT o.product_key, max(o.date) AS changed
                    FROM observations AS o JOIN products AS p ON p.product_key = o.product_key
                    WHERE o.price <> p.latest_price
                    GROUP BY o.product_key
                ) AS ch
                JOIN observations AS o ON o.product_key = ch.product_key AND o.date = ch.changed
            ) AS prev
            WHERE products.product_key = prev.product_key
            """
        )
        conn.execute("UPDATE products SET price_since = first_date WHERE price_since IS NULL")
        conn.execute(
            """
            UPDATE products SET is_current = (products.last_date >= r.cutoff AND products.last_date >= g.cutoff)
            FROM (SELECT retailer_key, date(max(last_date), '-7 days') AS cutoff FROM products GROUP BY retailer_key) AS r,
                 (SELECT date(max(last_date), ?) AS cutoff FROM products) AS g
            WHERE products.retailer_key = r.retailer_key
            """,
            (f"-{CURRENT_WINDOW_DAYS} days",),
        )
        # One window pass; an UPDATE ... FROM join on (name_key, retailer_key) has no
        # index at this point and runs for hours.
        conn.execute(
            """
            UPDATE products SET is_store_latest = 1 WHERE product_key IN (
                SELECT product_key FROM (
                    SELECT product_key, last_date,
                           max(last_date) OVER (PARTITION BY name_key, retailer_key) AS newest
                    FROM products
                ) WHERE last_date IS newest
            )
            """
        )
        conn.commit()
        write_unit_prices(conn, workers)


def _unit_prices(rows: list[tuple[int, str, float | None]]) -> list[tuple[float, str, int]]:
    """``(product_key, product_name, latest_price)`` -> ``(unit_price, unit, product_key)`` (worker process)."""
    out = []
    for product_key, product_name, price in rows:
        priced = unit_price(parse(product_name), price)
        if priced:
            out.append((priced[0], priced[1], product_key))
    return out


def write_unit_prices(conn: sqlite3.Connection, workers: int, chunk: int = 20_000) -> None:
    """Fill ``products.unit_price``/``unit_price_unit`` from each title and latest price, in worker processes."""
    print("Computing unit prices...")
    started = time.perf_counter()
    rows = conn.execute("SELECT product_key, product_name, latest_price FROM products").fetchall()
    chunks = [rows[i:i + chunk] for i in range(0, len(rows), chunk)]
    priced = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(_unit_prices, chunks):
            conn.executemany("UPDATE products SET unit_price = ?, unit_price_unit = ? WHERE product_key = ?", result)
            priced += len(result)
    conn.commit()
    print(f"  {priced:,} of {len(rows):,} products have a unit price ({time.perf_counter() - started:.0f}s)")


def ingest_raw(loader: Loader, raw_dir: Path, workers: int) -> set[str]:
    """Parse every dated raw CSV in parallel worker processes and load the rows.

    Prints progress and per-reason skip counts. Returns the set of retailers that
    got rows, which decides where the JSON fallback applies.
    """
    jobs, skipped = discover_raw_csvs(raw_dir)
    print(f"Raw CSVs: {len(jobs)} dated files to ingest from {raw_dir}")
    by_rel = {job[1]: job for job in jobs}
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
            loader.add(rel, retailer, date_str, stat.st_size, stat.st_mtime, rows)
            retailers.add(retailer)
            total_rows += len(rows)
            if done % 500 == 0:
                loader.conn.commit()
                print(f"  [{done}/{len(jobs)}] {total_rows:,} rows, {time.perf_counter() - started:.0f}s")
    loader.conn.commit()
    print(f"Raw CSVs: {total_rows:,} rows from {len(retailers)} retailers in {time.perf_counter() - started:.0f}s")
    for reason, count in sorted(skipped.items()):
        print(f"  skipped {count} files: {reason}")
    return retailers


def ingest_json_fallback(loader: Loader, json_dir: Path, covered: set[str]) -> None:
    """Load ``prices_json`` partitions for retailers not in ``covered``.

    Reads ``name``, ``category``, ``prices`` and the optional detail fields
    (``DETAIL_COLUMNS``, attached to the product's newest date) per product and adds
    one synthetic source row (``<file>.json#YYYY-MM-DD``) per date.
    """
    if not json_dir.is_dir():
        return
    for json_file in sorted(json_dir.glob("*.json")):
        retailer = retailer_from_stem(json_file.stem)
        if retailer in covered:
            print(f"JSON ignored: {json_file.name} ({retailer} has raw CSVs; fold them in with scripts/csv_to_json.py)")
            continue
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        by_day: dict[str, list[tuple]] = {}
        for product_id, product in payload.items():
            name = product.get("name") or str(product_id)
            category = product.get("category") or UNCATEGORIZED
            prices = {str(day): price for day, price in (product.get("prices") or {}).items() if price is not None}
            details = tuple(product.get(column) for column in DETAIL_COLUMNS)
            newest = max(prices) if prices else None
            for day, price in prices.items():
                row = (str(product_id), name, category, float(price))
                by_day.setdefault(day, []).append(row + details if day == newest else row)
        # One synthetic source row per date keeps the API's newest-N-files selection meaningful.
        stat = json_file.stat()
        for day in sorted(by_day):
            loader.add(f"{json_file.name}#{day}", retailer, day, stat.st_size, stat.st_mtime, by_day[day])
        print(f"JSON fallback: {retailer} ({sum(map(len, by_day.values())):,} rows from {json_file.name})")
    loader.conn.commit()


def build(data_dir: Path, db_path: Path, workers: int) -> None:
    """Build the database at ``db_path`` from ``data_dir`` and swap it in atomically.

    Joins split files, removes leftovers of a crashed build, writes into
    ``<db>.building`` with a scratch ``<db>.staging`` attached, creates indexes and
    views, runs ANALYZE, switches to WAL, deletes stale ``-wal``/``-shm`` files and
    replaces the target with ``os.replace``.
    """
    started = time.perf_counter()
    data_files.join(data_dir)
    building = db_path.with_name(db_path.name + ".building")
    staging = db_path.with_name(db_path.name + ".staging")
    for path in (building, staging):
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(building)
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA cache_size = -512000")
        conn.executescript(SCHEMA)
        # Staging lives in a separate file so its pages never bloat the served database.
        conn.execute("ATTACH DATABASE ? AS staging", (str(staging),))
        conn.execute("PRAGMA staging.journal_mode = OFF")
        conn.execute("PRAGMA staging.synchronous = OFF")
        conn.execute(
            "CREATE TABLE staging.obs (product_key INTEGER, date TEXT, price REAL, category_key INTEGER, source_key INTEGER)"
        )
        loader = Loader(conn)
        covered = ingest_raw(loader, data_dir / "raw", workers)
        ingest_json_fallback(loader, data_dir / "prices_json", covered)
        loader.finish(workers)
        conn.execute("DETACH DATABASE staging")
        print("Creating indexes and views...")
        conn.executescript(INDEXES + VIEWS)
        conn.execute("ANALYZE")
        conn.commit()
        products = conn.execute("SELECT count(*) FROM products").fetchone()[0]
        observations = conn.execute("SELECT count(*) FROM observations").fetchone()[0]
        retailers = conn.execute("SELECT count(*) FROM retailers").fetchone()[0]
        # WAL is what the read-only API connections expect.
        conn.execute("PRAGMA journal_mode = WAL")
    finally:
        conn.close()
        Path(staging).unlink(missing_ok=True)

    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    os.replace(building, db_path)
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(
        f"\nBuilt {db_path} ({size_mb:,.0f} MB): {retailers} retailers, {products:,} products, "
        f"{observations:,} observations in {time.perf_counter() - started:.0f}s"
    )


def main() -> int:
    """CLI entry point: ``--data-dir``, ``--db-path`` (default ``PRICES_DB_PATH`` or data/prices.db), ``--workers``."""
    parser = argparse.ArgumentParser(description="Build data/prices.db from committed scraper data")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--db-path", type=Path, default=Path(os.environ.get("PRICES_DB_PATH", DATA_DIR / "prices.db")))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    build(args.data_dir.resolve(), args.db_path.resolve(), args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
