#!/usr/bin/env python3
"""Convert scraped retailer CSVs into ``data/prices_json/<Group>_<Store>.json`` partitions.

The committed source of truth for converted retailers is one JSON file per retailer
with every product's full price history; ``scripts/build_database.py`` loads it like
any other partition. CSVs are parsed with the database build's own reader, folder
labels and header aliases, so a database built from the JSON matches one built from
the CSVs (the build keeps the last row per product and date, and a product's name and
category from its newest row; so does this script).

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

# Kept out of this repository even though upstream still has them (docs/DATA_CONTRACT.md).
DROPPED_RETAILERS = frozenset({"Communication / Xiaomi", "Communication / Teknoraks"})

Job = tuple[str, str, str, str]  # (absolute path, relative path, retailer label, ISO date)


class Layer:
    """One source's view of a retailer: prices per product and date, plus name and category.

    Rows are applied in file order; the last row for a product and date wins, and a
    product's name and category follow its newest-dated row (ties: the later row),
    exactly like ``build_database.Loader``.
    """

    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}
        self.meta: dict[str, tuple[str, str, str]] = {}  # product_id -> (date, name, category)

    def add(self, day: str, rows: Iterable[tuple[str, str, str, float]]) -> None:
        for product_id, name, category, price in rows:
            self.prices.setdefault(product_id, {})[day] = price
            current = self.meta.get(product_id)
            if current is None or day >= current[0]:
                self.meta[product_id] = (day, name, category)

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
        return layer


def merge(layers: list[Layer]) -> tuple[dict[str, dict[str, Any]], Counter]:
    """Merge layers, highest priority first, into a partition payload.

    Returns ``(payload, stats)``; ``stats`` counts prices kept from each layer
    (``layer0``, ``layer1``, ...) and conflicts where a lower layer had a different
    price for the same product and date (``conflicts``).
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
        candidates = [layer.meta[product_id] for layer in layers if product_id in layer.meta]
        _, name, category = max(enumerate(candidates), key=lambda item: (item[1][0], -item[0]))[1]
        by_day = dict(sorted(prices[product_id].items()))
        values = list(by_day.values())
        payload[product_id] = {
            "name": name,
            "category": category,
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
            payload, stats = merge([raw_layer, existing, source_layer])
            if not payload:
                print(f"skip {label}: no rows")
                continue
            days = {day for product in payload.values() for day in product["prices"]}
            print(
                f"{'would write' if dry_run else 'wrote'} {path.name}: {len(payload):,} products, {len(days)} dates; "
                f"{stats['layer0']:,} prices from {len(raw_used)} raw CSVs, {stats['layer1']:,} kept from JSON, "
                f"{stats['layer2']:,} new from --source"
                + (f", {stats['conflicts']:,} conflicting prices ignored" if stats["conflicts"] else "")
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
