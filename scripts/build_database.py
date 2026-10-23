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
4. Write the normalized schema (see SCHEMA), parse every title
   (domain.product_attributes) into match and family keys (domain.matching, with
   ``data/matching/brands.json`` and ``overrides.json``), clean scraper prices
   (domain.price_cleaning: missing, placeholder and dotted-thousands prices, case
   prices; ``clean_prices``), summarize products, give catalog products their
   permanent item and family IDs (``data/matching/ids.json``; ``write_items``),
   compute unit prices and atomically replace the target. Duplicate store folders
   are filed under one label (``RETAILER_ALIASES``).

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
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
for entry in (REPO_ROOT, Path(__file__).resolve().parent):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import data_files  # noqa: E402

from inflation_dashboard.domain.catalog import CATALOG_EXCLUDED_GROUPS, name_key, split_retailer  # noqa: E402
from inflation_dashboard.domain.matching import (  # noqa: E402
    Overrides,
    assign_ids,
    family_key,
    match_key,
    store_key,
)
from inflation_dashboard.domain.prices import (  # noqa: E402
    CATEGORY_COLUMNS,
    DETAIL_COLUMNS,
    ID_COLUMNS,
    NAME_COLUMNS,
    PRICE_COLUMNS,
    build_product_frame,
    header_key,
)
from inflation_dashboard.domain.price_cleaning import (  # noqa: E402
    CASE_PRICE_RETAILERS,
    PLACEHOLDER_PRICES,
    THOUSANDS_DOT_LIMIT,
    THOUSANDS_DOT_RETAILERS,
    is_placeholder,
    is_placeholder_family,
    reference_price,
    repair_thousands,
)
from inflation_dashboard.domain.product_attributes import brand_keys, parse, unit_basis  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
# Matching inputs under data/: brand list, permanent IDs, manual corrections.
BRANDS_FILE = Path("matching") / "brands.json"
IDS_FILE = Path("matching") / "ids.json"
OVERRIDES_FILE = Path("matching") / "overrides.json"

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
-- m or m2) parsed from the title; NULL when the title has no contents size or the
-- price is a case price. is_case_price marks stores whose prices are whole cases
-- (domain.price_cleaning.CASE_PRICE_RETAILERS); the catalog never ranks them cheapest.
-- match_key / family_key (domain.matching) are parsed from the title, after
-- data/matching/overrides.json; pack is the number of items in the package. item_id
-- is the permanent catalog product (items) for products outside
-- CATALOG_EXCLUDED_GROUPS whose item has an ID; is_pack_option marks multipacks of
-- an item that is also sold in smaller packs (items.main_pack).
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
    is_case_price INTEGER NOT NULL DEFAULT 0,
    match_key TEXT,
    family_key TEXT,
    pack INTEGER NOT NULL DEFAULT 1,
    item_id INTEGER REFERENCES items,
    is_pack_option INTEGER NOT NULL DEFAULT 0,
    UNIQUE (retailer_key, product_id)
);
-- One row per catalog product (one match key) with its permanent ID from
-- data/matching/ids.json. main_pack is the smallest pack its current products come in.
CREATE TABLE items (
    item_id INTEGER PRIMARY KEY,
    match_key TEXT NOT NULL UNIQUE,
    family_id INTEGER REFERENCES families,
    main_pack INTEGER NOT NULL DEFAULT 1
);
-- One row per family (the product without its size) of two or more items.
CREATE TABLE families (
    family_id INTEGER PRIMARY KEY,
    family_key TEXT NOT NULL UNIQUE,
    item_count INTEGER NOT NULL
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
CREATE INDEX idx_products_item ON products(item_id);
CREATE INDEX idx_items_family ON items(family_id);
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
# Stores the scrapers write under two folder names (old label -> label written now);
# the build files both under one label. Products with the same product_id merge.
RETAILER_ALIASES = {
    "Cosmetics / Watson": "Cosmetics / Watsons",
    "ConstructionSuppliesMarkets / Koçtaş": "ConstructionSuppliesMarkets / Koctas",
    "Communication / Vatan Computer": "Communication / VatanComputer",
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


@dataclass
class Matching:
    """Matching inputs from ``data/matching`` (each file optional): folded brand keys,
    manual overrides and the permanent IDs of ``ids.json``."""

    brands: list[str] = field(default_factory=list)
    overrides: Overrides = field(default_factory=Overrides)
    item_ids: dict[str, int] = field(default_factory=dict)
    family_ids: dict[str, int] = field(default_factory=dict)
    next_item_id: int = 1
    next_family_id: int = 1


def read_ids(path: Path) -> tuple[dict[str, int], dict[str, int], int, int]:
    """``ids.json`` as ``(item_ids, family_ids, next_item_id, next_family_id)``; empty when missing."""
    if not path.exists():
        return {}, {}, 1, 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    items, families = payload.get("items", {}), payload.get("families", {})
    next_item = max(payload.get("next_item_id", 1), max(items.values(), default=0) + 1)
    next_family = max(payload.get("next_family_id", 1), max(families.values(), default=0) + 1)
    return items, families, next_item, next_family


def write_ids(path: Path, items: dict[str, int], families: dict[str, int], next_item: int, next_family: int) -> None:
    """Write ``ids.json``: one entry per line in ID order, so new IDs append and diffs stay small."""

    def block(ids: dict[str, int]) -> str:
        lines = [f"{json.dumps(key, ensure_ascii=False)}: {value}" for key, value in sorted(ids.items(), key=lambda kv: kv[1])]
        return "{\n" + ",\n".join(lines) + ("\n}" if lines else "}")

    text = (
        "{\n"
        '"description": "Permanent catalog item and family IDs by match/family key '
        '(inflation_dashboard.domain.matching); appended by scripts/assign_ids.py, never renumbered.",\n'
        f'"next_item_id": {next_item},\n'
        f'"next_family_id": {next_family},\n'
        f'"items": {block(items)},\n'
        f'"families": {block(families)}\n'
        "}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_matching(data_dir: Path) -> Matching:
    """Read ``brands.json``, ``overrides.json`` and ``ids.json`` from ``data_dir/matching``."""
    brands_path, overrides_path = data_dir / BRANDS_FILE, data_dir / OVERRIDES_FILE
    brands = (
        [brand["key"] for brand in json.loads(brands_path.read_text(encoding="utf-8"))["brands"]]
        if brands_path.exists()
        else []
    )
    overrides = (
        Overrides.from_json(json.loads(overrides_path.read_text(encoding="utf-8")))
        if overrides_path.exists()
        else Overrides()
    )
    return Matching(brands, overrides, *read_ids(data_dir / IDS_FILE))


class Loader:
    """Assigns integer keys and streams observations into an append-only staging table.

    Observations are staged in arrival order; ``finish`` keeps the last row per
    (product, date), matching INSERT OR REPLACE semantics, and writes them
    clustered by (product_key, date).
    """

    def __init__(self, conn: sqlite3.Connection, matching: Matching | None = None) -> None:
        self.conn = conn
        self.matching = matching or Matching()
        self.retailers: dict[str, int] = {}
        self.categories: dict[str, int] = {}
        # (retailer_key, product_id) -> [product_key, latest_date, product_name, category_key]
        self.products: dict[tuple[int, str], list] = {}
        # product_key -> {detail: (date, value)}, the newest non-empty value per detail
        self.details: dict[int, dict[str, tuple[str, object]]] = {}
        self.ingested_at = datetime.now(timezone.utc).isoformat()
        self.staged_rows = 0
        # Counts for the build summary: relabelled rows (RETAILER_ALIASES) and clean_prices rules,
        # then matching (write_match_keys, write_items).
        self.cleanup: Counter = Counter()
        self.matched: Counter = Counter()

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
        keep their newest non-empty value per product. Retailers in
        ``RETAILER_ALIASES`` are stored under their alias.
        """
        if retailer in RETAILER_ALIASES:
            self.cleanup[f"rows filed from {retailer} under {RETAILER_ALIASES[retailer]}"] += len(rows)
            retailer = RETAILER_ALIASES[retailer]
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

        Inserts retailers, categories and products (with their details), parses every
        title into match/family keys and pack (``write_match_keys``), copies the staged
        rows into ``observations`` keeping the last staged row per (product, date),
        cleans prices (``clean_prices``) and flags case prices (``is_case_price``), then
        fills each product's first/last date, min/max price, observation count, latest
        price, latest price change (``previous_price``, ``price_since``), ``is_current``,
        item and family (``write_items``), ``is_store_latest`` and unit price
        (``write_unit_prices``).
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
        basis = write_match_keys(conn, self.retailers, self.matching, workers, self.matched)
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
        self.cleanup.update(clean_prices(conn, self.retailers))
        case_keys = [key for name, key in self.retailers.items() if name in CASE_PRICE_RETAILERS]
        flagged = conn.execute(
            f"UPDATE products SET is_case_price = 1 WHERE retailer_key IN ({','.join('?' * len(case_keys))})", case_keys
        ).rowcount
        self.cleanup["products flagged as case prices"] = flagged
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
            UPDATE products SET is_current = coalesce(products.last_date >= r.cutoff AND products.last_date >= g.cutoff, 0)
            FROM (SELECT retailer_key, date(max(last_date), '-7 days') AS cutoff FROM products GROUP BY retailer_key) AS r,
                 (SELECT date(max(last_date), ?) AS cutoff FROM products) AS g
            WHERE products.retailer_key = r.retailer_key
            """,
            (f"-{CURRENT_WINDOW_DAYS} days",),
        )
        conn.commit()
        write_items(conn, self.matching, self.matched)
        # One window pass; an UPDATE ... FROM join on (item, pack, retailer_key) has no
        # index at this point and runs for hours. Products outside the catalog use name_key.
        conn.execute(
            """
            UPDATE products SET is_store_latest = 1 WHERE product_key IN (
                SELECT product_key FROM (
                    SELECT product_key, last_date,
                           max(last_date) OVER (
                               PARTITION BY coalesce('i' || item_id || '#' || pack, 'n' || name_key), retailer_key
                           ) AS newest
                    FROM products
                ) WHERE last_date IS newest
            )
            """
        )
        conn.commit()
        write_unit_prices(conn, basis)


_PARSER_BRANDS: frozenset[tuple[str, ...]] = frozenset()


def _init_parser(brands: list[str]) -> None:
    """Worker initializer: the brand list ``parse`` matches titles against."""
    global _PARSER_BRANDS
    _PARSER_BRANDS = brand_keys(brands)


def _parse_titles(rows: list[tuple[int, str, str | None]]) -> list[tuple]:
    """``(product_key, product_name, brand)`` -> ``(product_key, match_key, family_key, pack,
    unit amount, unit)`` (worker process; ``domain.matching``, ``unit_basis``)."""
    out = []
    for product_key, product_name, brand in rows:
        parsed = parse(product_name, _PARSER_BRANDS, brand)
        amount, unit = unit_basis(parsed) or (None, None)
        out.append((product_key, match_key(parsed), family_key(parsed), parsed.pack, amount, unit))
    return out


def write_match_keys(
    conn: sqlite3.Connection, retailers: dict[str, int], matching: Matching, workers: int, counts: Counter,
    chunk: int = 20_000,
) -> dict[int, tuple[float, str]]:
    """Parse every title in worker processes; fill ``products.match_key``, ``family_key`` and ``pack``.

    Products of ``CATALOG_EXCLUDED_GROUPS`` get no keys. A title without brand, word
    or code gets its own ``store_key``; ``matching.overrides`` are applied last.
    Returns ``{product_key: (amount, unit)}``, what ``write_unit_prices`` divides
    the latest price by.
    """
    print("Parsing titles into match keys...")
    started = time.perf_counter()
    names = {key: name for name, key in retailers.items()}
    excluded = {key for name, key in retailers.items() if split_retailer(name)[0] in CATALOG_EXCLUDED_GROUPS}
    rows = conn.execute("SELECT product_key, retailer_key, product_id, product_name, brand FROM products").fetchall()
    owner = {product_key: (retailer_key, product_id) for product_key, retailer_key, product_id, _, _ in rows}
    jobs = [(product_key, name, brand) for product_key, _, _, name, brand in rows]
    basis: dict[int, tuple[float, str]] = {}
    updates = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_parser, initargs=(matching.brands,)) as pool:
        for result in pool.map(_parse_titles, [jobs[i:i + chunk] for i in range(0, len(jobs), chunk)]):
            for product_key, key, family, pack, amount, unit in result:
                if amount:
                    basis[product_key] = (amount, unit)
                retailer_key, product_id = owner[product_key]
                if retailer_key in excluded:
                    updates.append((None, None, pack, product_key))
                    continue
                retailer = names[retailer_key]
                if key is None:
                    counts["products without a usable title (own item)"] += 1
                final = matching.overrides.apply(retailer, product_id, key or store_key(retailer, product_id))
                if key is not None and final != key:
                    counts["products moved by overrides.json"] += 1
                updates.append((final, family, pack, product_key))
    conn.executemany("UPDATE products SET match_key = ?, family_key = ?, pack = ? WHERE product_key = ?", updates)
    conn.commit()
    counts["multipack products (pack > 1)"] = sum(1 for update in updates if update[2] > 1)
    print(f"  {len(rows):,} titles parsed ({time.perf_counter() - started:.0f}s)")
    return basis


def write_items(conn: sqlite3.Connection, matching: Matching, counts: Counter) -> None:
    """Fill ``items``, ``families``, ``products.item_id`` and ``products.is_pack_option``.

    An item is one match key that has a current product or already has an ID in
    ``ids.json``; its family is the most common family key of its products, and a
    family gets a row when it has two or more items or already has an ID. Keys
    without an ID get provisional ones (``domain.matching.assign_ids``, the same IDs
    ``scripts/assign_ids.py`` commits). ``main_pack`` is the smallest pack among the
    item's current products (all its products when none is current); bigger packs
    are pack options.
    """
    print("Assigning item and family IDs...")
    rows = conn.execute(
        "SELECT match_key, family_key, pack, is_current, product_key FROM products WHERE match_key IS NOT NULL"
    ).fetchall()
    keys = {key for key, _, _, current, _ in rows if current} | {key for key, *_ in rows if key in matching.item_ids}
    new_items, next_item = assign_ids(matching.item_ids, keys, matching.next_item_id)
    item_ids = {key: matching.item_ids.get(key) or new_items[key] for key in keys}

    votes: dict[str, Counter] = defaultdict(Counter)
    packs: dict[str, list[set[int]]] = defaultdict(lambda: [set(), set()])  # [current packs, all packs]
    for key, family, pack, current, _ in rows:
        if key not in item_ids:
            continue
        if family:
            votes[key][family] += 1
        packs[key][1].add(pack)
        if current:
            packs[key][0].add(pack)
    item_family = {key: min(v.items(), key=lambda kv: (-kv[1], kv[0]))[0] for key, v in votes.items()}
    members: Counter = Counter(item_family.values())
    family_keys = {family for family, n in members.items() if n >= 2 or family in matching.family_ids}
    new_families, next_family = assign_ids(matching.family_ids, family_keys, matching.next_family_id)
    family_ids = {family: matching.family_ids.get(family) or new_families[family] for family in family_keys}

    conn.executemany("INSERT INTO families VALUES (?, ?, ?)", [(fid, f, members[f]) for f, fid in family_ids.items()])
    main_pack = {key: min(packs[key][0] or packs[key][1]) for key in item_ids}
    conn.executemany(
        "INSERT INTO items VALUES (?, ?, ?, ?)",
        [(item_id, key, family_ids.get(item_family.get(key, "")), main_pack[key]) for key, item_id in item_ids.items()],
    )
    # Per product by key: an UPDATE ... FROM join on match_key has no index here.
    updates = [
        (item_ids[key], int(pack > main_pack[key]), product_key)
        for key, _, pack, _, product_key in rows
        if key in item_ids
    ]
    conn.executemany("UPDATE products SET item_id = ?, is_pack_option = ? WHERE product_key = ?", updates)
    pack_options = sum(update[1] for update in updates)
    conn.commit()
    counts["items"] = len(item_ids)
    counts[f"items with a provisional ID (next {next_item:,}; run scripts/assign_ids.py)"] = len(new_items)
    counts["families (2+ items)"] = len(family_ids)
    counts[f"families with a provisional ID (next {next_family:,})"] = len(new_families)
    counts["pack-option products"] = pack_options


def write_unit_prices(conn: sqlite3.Connection, basis: dict[int, tuple[float, str]]) -> None:
    """Fill ``products.unit_price``/``unit_price_unit``: ``latest_price`` over the parsed contents (``basis``)."""
    print("Computing unit prices...")
    rows = conn.execute(
        "SELECT product_key, latest_price FROM products WHERE is_case_price = 0 AND latest_price > 0"
    ).fetchall()
    updates = [
        (price / basis[product_key][0], basis[product_key][1], product_key)
        for product_key, price in rows
        if product_key in basis
    ]
    conn.executemany("UPDATE products SET unit_price = ?, unit_price_unit = ? WHERE product_key = ?", updates)
    conn.commit()
    print(f"  {len(updates):,} of {len(rows):,} priced products have a unit price")


# Same item for price references: same match key and pack (name_key outside the catalog).
_PEER_KEY = "coalesce('m' || {p}match_key, 'n' || {p}name_key) || '#' || {p}pack"


def _histories(conn: sqlite3.Connection, candidates_sql: str, params: list) -> dict[int, tuple[int, str, list]]:
    """``{product_key: (retailer_key, peer key, [(date, price), ...])}`` for every product
    sharing a match key and pack (``_PEER_KEY``) with the products ``candidates_sql`` selects."""
    histories: dict[int, tuple[int, str, list]] = {}
    for product_key, retailer_key, key, day, price in conn.execute(
        f"""
        SELECT p.product_key, p.retailer_key, {_PEER_KEY.format(p="p.")}, o.date, o.price
        FROM products AS p JOIN observations AS o ON o.product_key = p.product_key
        WHERE {_PEER_KEY.format(p="p.")} IN (
            SELECT {_PEER_KEY.format(p="")} FROM products WHERE product_key IN ({candidates_sql})
        )
        """,
        params,
    ):
        histories.setdefault(product_key, (retailer_key, key, []))[2].append((day, price))
    return histories


def _peer_references(histories: dict[int, tuple[int, str, list]], excluded: set[int]) -> dict[str, list[tuple[int, float]]]:
    """``{peer key: [(retailer_key, reference price), ...]}`` from products outside ``excluded`` retailers."""
    peers: dict[str, list[tuple[int, float]]] = {}
    for retailer_key, key, history in histories.values():
        if retailer_key in excluded:
            continue
        reference = reference_price(price for _, price in history)
        if reference is not None:
            peers.setdefault(key, []).append((retailer_key, reference))
    return peers


def _peer_reference(peers: dict[str, list[tuple[int, float]]], key: str, retailer_key: int) -> float | None:
    """Median reference price of the same item in other stores."""
    references = [reference for other, reference in peers.get(key, ()) if other != retailer_key]
    return median(references) if references else None


def clean_prices(conn: sqlite3.Connection, retailers: dict[str, int]) -> Counter:
    """Apply ``domain.price_cleaning`` to ``observations`` and return counts per rule.

    Deletes prices of 0 or less, repairs or deletes dotted-thousands prices of
    ``THOUSANDS_DOT_RETAILERS``, then deletes 999-family placeholder prices. Peers
    (same match key and pack, other stores) never include ``CASE_PRICE_RETAILERS``; the
    dotted-thousands stores are left out of their own repair's peers.
    """
    counts: Counter = Counter()
    print("Cleaning prices...")
    counts["prices <= 0 dropped"] = conn.execute("DELETE FROM observations WHERE price <= 0").rowcount
    case_keys = {key for name, key in retailers.items() if name in CASE_PRICE_RETAILERS}

    thousands_keys = [key for name, key in retailers.items() if name in THOUSANDS_DOT_RETAILERS]
    if thousands_keys:
        marks = ",".join("?" * len(thousands_keys))
        candidates = (
            f"SELECT o.product_key FROM observations AS o JOIN products AS p ON p.product_key = o.product_key "
            f"WHERE p.retailer_key IN ({marks}) AND o.price < ?"
        )
        histories = _histories(conn, candidates, [*thousands_keys, THOUSANDS_DOT_LIMIT])
        peers = _peer_references(histories, case_keys | set(thousands_keys))
        updates, deletes, products = [], [], set()
        for product_key, (retailer_key, key, history) in histories.items():
            if retailer_key not in thousands_keys or all(price >= THOUSANDS_DOT_LIMIT for _, price in history):
                continue
            own = reference_price(price for _, price in history if price >= THOUSANDS_DOT_LIMIT)
            peer = _peer_reference(peers, key, retailer_key)
            for day, price in history:
                repaired = repair_thousands(price, own, peer)
                if repaired is None:
                    deletes.append((product_key, day))
                elif repaired != price:
                    updates.append((repaired, product_key, day))
                    products.add(product_key)
        conn.executemany("UPDATE observations SET price = ? WHERE product_key = ? AND date = ?", updates)
        conn.executemany("DELETE FROM observations WHERE product_key = ? AND date = ?", deletes)
        counts[f"dotted-thousands prices repaired x1000 ({len(products):,} products)"] = len(updates)
        counts["dotted-thousands prices dropped (unconfirmed)"] = len(deletes)

    family = sorted(PLACEHOLDER_PRICES)
    candidates = f"SELECT product_key FROM observations WHERE price IN ({','.join('?' * len(family))})"
    histories = _histories(conn, candidates, family)
    peers = _peer_references(histories, case_keys)
    deletes, products, kept = [], set(), 0
    for product_key, (retailer_key, key, history) in histories.items():
        if not any(is_placeholder_family(price) for _, price in history):
            continue
        own = reference_price(price for _, price in history)
        peer = _peer_reference(peers, key, retailer_key)
        for day, price in history:
            if is_placeholder(price, own, peer):
                deletes.append((product_key, day))
                products.add(product_key)
            elif is_placeholder_family(price):
                kept += 1
    conn.executemany("DELETE FROM observations WHERE product_key = ? AND date = ?", deletes)
    counts[f"placeholder prices dropped ({len(products):,} products)"] = len(deletes)
    counts["999-family prices kept as real"] = kept
    conn.commit()
    return counts


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
        loader = Loader(conn, load_matching(data_dir))
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
    print("Price clean-up (domain.price_cleaning, RETAILER_ALIASES):")
    for rule, count in loader.cleanup.items():
        print(f"  {count:>9,}  {rule}")
    print("Matching (domain.matching, data/matching):")
    for rule, count in loader.matched.items():
        print(f"  {count:>9,}  {rule}")


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
