#!/usr/bin/env python3
"""Convert scraped retailer CSVs into ``data/prices_json/<Group>_<Store>.json`` partitions.

The committed source of truth for converted retailers is one JSON file per retailer
with every product's full price history; ``scripts/build_database.py`` loads it like
any other partition. CSVs are parsed with the database build's own reader, folder
labels and header aliases, so a database built from the JSON matches one built from
the CSVs (the build keeps the last row per product and date, and a product's name and
category from its newest row; so does this script). Product details scrapers send
(``brand``, ``barcode``, ``image_url``, ``product_url``, ``regular_price``) are kept
as optional JSON fields: the newest non-empty value of each wins, and the regular
price only when it was sent on the product's newest date.

Two uses:

* Replace this repository's CSVs (no ``--source``): every retailer selected under
  ``data/raw`` is written to JSON and its ingested CSVs are deleted. Files the build
  skips (undated, unreadable, no price column) stay where they are.
* Import from the upstream data repository (``--source <clone>/InflationItems/Datas``):
  new products and dates are merged into each retailer's JSON. Prices already in this
  repository are never overwritten. A retailer's remaining ``data/raw`` CSVs are folded
  into its JSON and deleted, because the build ignores a JSON partition while the
  retailer still has raw CSVs.

Priority for the same product and date: ``data/raw`` CSV, then the existing JSON, then
``--source``. Stores this repository has dropped (``DROPPED_RETAILERS``) are skipped.

Usage:
    python scripts/csv_to_json.py --retailer "Markets / Migros"
    python scripts/csv_to_json.py --retailers-file retailers.txt
    python scripts/csv_to_json.py --source ../InflationResearchStudy/InflationItems/Datas
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterable

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
for path in (SCRIPTS_DIR, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_database  # noqa: E402
import data_files  # noqa: E402

from inflation_dashboard.domain.prices import DETAIL_COLUMNS  # noqa: E402

# Kept out of this repository even though upstream still has them (docs/DATA_CONTRACT.md).
DROPPED_RETAILERS = frozenset({"Communication / Xiaomi", "Communication / Teknoraks"})

Job = tuple[str, str, str, str]  # (absolute path, relative path, retailer label, ISO date)


Details = dict[str, tuple[str, Any]]  # detail column -> (date, value)


def newer_details(target: Details, source: Details) -> None:
    """Copy into ``target`` each detail ``source`` has with a date at least as new."""
    for column, (day, value) in source.items():
        if column not in target or day >= target[column][0]:
            target[column] = (day, value)


class Layer:
    """One source's view of a retailer: prices per product and date, plus name and category.

    Rows are applied in file order; the last row for a product and date wins, and a
    product's name and category follow its newest-dated row (ties: the later row),
    exactly like ``build_database.Loader``. Details keep their newest non-empty value.
    """

    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}
        self.meta: dict[str, tuple[str, str, str]] = {}  # product_id -> (date, name, category)
        self.details: dict[str, Details] = {}
        self.ids_by_name: dict[str, set[str]] = {}  # every name a non-name id was seen with

    def add(self, day: str, rows: Iterable[tuple]) -> None:
        """Apply ``(product_id, name, category, price, *details)`` rows scraped on ``day``."""
        for product_id, name, category, price, *details in rows:
            self.prices.setdefault(product_id, {})[day] = price
            if product_id != name:
                self.ids_by_name.setdefault(name, set()).add(product_id)
            current = self.meta.get(product_id)
            if current is None or day >= current[0]:
                self.meta[product_id] = (day, name, category)
            if any(value is not None for value in details):
                newer_details(
                    self.details.setdefault(product_id, {}),
                    {column: (day, value) for column, value in zip(DETAIL_COLUMNS, details) if value is not None},
                )

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "Layer":
        """Read a partition the way ``build_database.ingest_json_fallback`` does."""
        layer = cls()
        for product_id, product in payload.items():
            prices = {str(day): float(price) for day, price in (product.get("prices") or {}).items() if price is not None}
            if not prices:
                continue
            layer.prices[str(product_id)] = prices
            layer.meta[str(product_id)] = (
                max(prices),
                product.get("name") or str(product_id),
                product.get("category") or build_database.UNCATEGORIZED,
            )
            if layer.meta[str(product_id)][1] != str(product_id):
                layer.ids_by_name.setdefault(layer.meta[str(product_id)][1], set()).add(str(product_id))
            # Stored details count as seen on the product's newest date.
            details = {c: (max(prices), product[c]) for c in DETAIL_COLUMNS if product.get(c) is not None}
            if details:
                layer.details[str(product_id)] = details
        return layer


def rekey_by_name(layers: list[Layer]) -> int:
    """Move products keyed by their name onto the retailer's own product id.

    Scrapers that started writing an id column (A101 ``urun_id`` since 2026-08) left
    older rows keyed by the product name. A name-keyed product joins the id that
    was ever scraped with exactly that name, if only one id was; its prices fill
    dates the id lacks. When several ids share the name, the name-keyed history
    stays but loses the dates from the first of those ids' prices on, which the ids
    already cover. Returns the number of products moved or trimmed.
    """
    ids_by_name: dict[str, set[str]] = {}
    for layer in layers:
        for name, ids in layer.ids_by_name.items():
            ids_by_name.setdefault(name, set()).update(ids)
    all_ids = set().union(*ids_by_name.values()) if ids_by_name else set()
    moved = 0
    for layer in layers:
        for product_id in [pid for pid in layer.prices if pid not in all_ids and len(ids_by_name.get(pid, ())) > 1]:
            first = min(min(lay.prices[i]) for i in ids_by_name[product_id] for lay in layers if lay.prices.get(i))
            kept = {day: price for day, price in layer.prices[product_id].items() if day < first}
            if len(kept) == len(layer.prices[product_id]):
                continue
            if kept:
                layer.prices[product_id] = kept
                layer.meta[product_id] = (max(kept), *layer.meta[product_id][1:])
            else:
                del layer.prices[product_id], layer.meta[product_id]
                layer.details.pop(product_id, None)
            moved += 1
        for product_id in [pid for pid in layer.prices if pid not in all_ids and len(ids_by_name.get(pid, ())) == 1]:
            (target,) = ids_by_name[product_id]
            prices = layer.prices.pop(product_id)
            meta = layer.meta.pop(product_id)
            if product_id in layer.details:
                newer_details(layer.details.setdefault(target, {}), layer.details.pop(product_id))
            merged = layer.prices.setdefault(target, {})
            for day, price in prices.items():
                merged.setdefault(day, price)
            current = layer.meta.get(target)
            if current is None or meta[0] > current[0]:
                layer.meta[target] = meta
            moved += 1
    return moved


def merge(layers: list[Layer]) -> tuple[dict[str, dict[str, Any]], Counter]:
    """Merge layers, highest priority first, into a partition payload.

    Returns ``(payload, stats)``; ``stats`` counts prices kept from each layer
    (``layer0``, ``layer1``, ...) and conflicts where a lower layer had a different
    price for the same product and date (``conflicts``). The newest row names the
    product; its category is the newest one that is not ``Uncategorized``. Each
    detail is the newest one across layers (ties: the higher-priority layer); the
    regular price is dropped unless it is from the product's newest date.
    """
    stats: Counter = Counter()
    prices: dict[str, dict[str, float]] = {}
    for index, layer in enumerate(layers):
        for product_id, by_day in layer.prices.items():
            merged = prices.setdefault(product_id, {})
            for day, price in by_day.items():
                if day not in merged:
                    merged[day] = price
                    stats[f"layer{index}"] += 1
                elif merged[day] != price:
                    stats["conflicts"] += 1
    payload = {}
    for product_id in sorted(prices):
        # Newest row decides name and category; on a tie the higher-priority layer wins.
        # A real category beats Uncategorized (older imports dropped category columns).
        candidates = [layer.meta[product_id] for layer in layers if product_id in layer.meta]
        newest = lambda item: (item[1][0], -item[0])  # noqa: E731
        _, name, category = max(enumerate(candidates), key=newest)[1]
        categorized = [c for c in enumerate(candidates) if c[1][2] != build_database.UNCATEGORIZED]
        if categorized:
            category = max(categorized, key=newest)[1][2]
        by_day = dict(sorted(prices[product_id].items()))
        values = list(by_day.values())
        details: Details = {}
        for layer in reversed(layers):  # higher-priority layers last, so they win ties
            newer_details(details, layer.details.get(product_id, {}))
        newest_day = next(reversed(by_day))
        product = {"name": name, "category": category}
        for column in DETAIL_COLUMNS:
            if column in details and (column != "regular_price" or details[column][0] == newest_day):
                product[column] = details[column][1]
        payload[product_id] = {
            **product,
            "latest_price": values[-1],
            "min_price": min(values),
            "max_price": max(values),
            "prices": by_day,
        }
    return payload, stats


def write_partition(path: Path, payload: dict[str, dict[str, Any]]) -> None:
    """Write one product per line: valid JSON, compact, and diffable per product."""
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("{\n")
        for index, (product_id, product) in enumerate(payload.items()):
            sep = "," if index < len(payload) - 1 else ""
            handle.write(f"{json.dumps(product_id, ensure_ascii=False)}: {json.dumps(product, ensure_ascii=False)}{sep}\n")
        handle.write("}\n")
    os.replace(tmp, path)


def parse_jobs(pool: ProcessPoolExecutor, jobs: list[Job], problems: Counter) -> tuple[Layer, list[Job]]:
    """Parse ``jobs`` (in order) into a layer; return it and the jobs that produced rows."""
    layer, used = Layer(), []
    by_rel = {job[1]: job for job in jobs}
    for rel, rows, problem in pool.map(build_database._ingest_file, jobs, chunksize=4):
        if problem:
            problems[problem] += 1
            continue
        finite = [row for row in rows if math.isfinite(row[3])]
        problems["non-finite prices dropped"] += len(rows) - len(finite)
        job = by_rel[rel]
        layer.add(job[3], finite)
        used.append(job)
    return layer, used


def remove_files(paths: Iterable[str], raw_dir: Path) -> None:
    """Delete converted CSVs and any folders under ``raw_dir`` they leave empty."""
    parents = set()
    for path in paths:
        Path(path).unlink()
        parents.add(Path(path).parent)
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        while parent != raw_dir and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def group_jobs(jobs: list[Job]) -> dict[str, list[Job]]:
    by_retailer: dict[str, list[Job]] = {}
    for job in jobs:
        by_retailer.setdefault(job[2], []).append(job)
    return by_retailer


def convert(
    data_dir: Path,
    sources: list[Path],
    retailers: set[str] | None,
    workers: int,
    dry_run: bool = False,
) -> int:
    """Convert the selected retailers; return the process exit code."""
    raw_dir = data_dir / "raw"
    json_dir = data_dir / "prices_json"
    if not dry_run:
        json_dir.mkdir(parents=True, exist_ok=True)
        data_files.join(data_dir)  # split JSON partitions must be whole before merging

    raw_jobs = group_jobs(build_database.discover_raw_csvs(raw_dir)[0]) if raw_dir.is_dir() else {}
    source_jobs: dict[str, list[Job]] = {}
    for source in sources:
        for label, jobs in group_jobs(build_database.discover_raw_csvs(source)[0]).items():
            source_jobs.setdefault(label, []).extend(jobs)

    available = set(source_jobs) if sources else set(raw_jobs)
    if retailers is not None:
        unknown = sorted(retailers - available)
        if unknown:
            print(f"[ERROR] No ingestible CSVs for: {', '.join(unknown)}", file=sys.stderr)
            return 1
        available &= retailers
    dropped = sorted(available & DROPPED_RETAILERS)
    targets = sorted(available - DROPPED_RETAILERS)
    for label in dropped:
        print(f"skip {label}: dropped from this repository")
    try:
        stems = {label: build_database.retailer_stem(label) for label in targets}
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    problems: Counter = Counter()
    totals: Counter = Counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for label in targets:
            path = json_dir / f"{stems[label]}.json"
            existing = Layer.from_json(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else Layer()
            raw_layer, raw_used = parse_jobs(pool, raw_jobs.get(label, []), problems)
            source_layer, _ = parse_jobs(pool, source_jobs.get(label, []), problems) if sources else (Layer(), [])
            layers = [raw_layer, existing, source_layer]
            rekeyed = rekey_by_name(layers)
            payload, stats = merge(layers)
            if not payload:
                print(f"skip {label}: no rows")
                continue
            days = {day for product in payload.values() for day in product["prices"]}
            print(
                f"{'would write' if dry_run else 'wrote'} {path.name}: {len(payload):,} products, {len(days)} dates; "
                f"{stats['layer0']:,} prices from {len(raw_used)} raw CSVs, {stats['layer1']:,} kept from JSON, "
                f"{stats['layer2']:,} new from --source"
                + (f", {stats['conflicts']:,} conflicting prices ignored" if stats["conflicts"] else "")
                + (f", {rekeyed:,} name-keyed products moved to their id" if rekeyed else "")
            )
            totals.update(stats)
            totals["retailers"] += 1
            totals["raw files"] += len(raw_used)
            if dry_run:
                continue
            write_partition(path, payload)
            remove_files((job[0] for job in raw_used), raw_dir)

    verb = "Would convert" if dry_run else "Converted"
    print(
        f"{verb} {totals['retailers']} retailers; {totals['raw files']} raw CSVs "
        f"{'would be' if dry_run else ''} removed; {totals['layer2']:,} new prices from --source."
    )
    for reason, count in sorted(problems.items()):
        if count:
            print(f"  skipped {count} {'prices' if 'prices' in reason else 'files'}: {reason}")
    if not dry_run:
        print("Next: uv run python scripts/data_files.py check (split files over 85 MB), then rebuild the database.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data", help="Data directory (default: data/).")
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=[],
        help="CSV tree laid out like data/raw (e.g. <clone>/InflationItems/Datas); repeatable. "
        "Without it, this repository's data/raw CSVs are converted.",
    )
    parser.add_argument("--retailer", action="append", help="Retailer label to convert, e.g. 'Markets / Migros'; repeatable.")
    parser.add_argument("--retailers-file", type=Path, help="File with one retailer label per line.")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1), help="Parser processes.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change; write and delete nothing.")
    args = parser.parse_args()

    retailers: set[str] | None = None
    if args.retailer or args.retailers_file:
        retailers = set(args.retailer or [])
        if args.retailers_file:
            lines = args.retailers_file.read_text(encoding="utf-8").splitlines()
            retailers |= {line.strip() for line in lines if line.strip()}
    if not args.source and retailers is None:
        parser.error("converting data/raw needs --retailer or --retailers-file (use --source to import)")
    for source in args.source:
        if not source.is_dir():
            parser.error(f"--source is not a directory: {source}")
    return convert(args.data_dir.resolve(), [s.resolve() for s in args.source], retailers, args.workers, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
