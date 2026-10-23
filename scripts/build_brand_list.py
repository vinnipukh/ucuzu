#!/usr/bin/env python3
"""Build ``data/matching/brands.json``, the brand list the title parser matches against.

Sources, all from the committed ``data/`` tree:

1. Retailer brand columns: the ``brand`` field of ``data/prices_json`` products
   (A101 ``marka``, Macrocenter/GoldenRose/DR/Nezih ``Brand`` …). A value is kept
   when at least one title carrying it starts with it, so publisher or supplier
   names that never lead a title are dropped.
2. The Watsons brand list: the categories of ``Cosmetics_Watson.json`` (that old
   scrape filed every product under its brand).
3. Brands learned from titles: a first word that starts current titles in
   ``MIN_STORES`` or more stores and is the first word in at least
   ``MIN_FIRST_SHARE`` of the current titles that contain it (generic words such as
   "domates" also appear mid-title). When one second word follows it in at least
   ``MIN_BIGRAM_SHARE`` of those titles (and there are ``MIN_BIGRAM_TITLES`` or
   more), a first word of up to ``MAX_BIGRAM_FIRST_LEN`` letters becomes a two-word
   brand (``air wick``, ``dr oetker``).
4. Reviewed corrections in ``data/matching/brand_overrides.json``:
   ``{"add": [names], "remove": [keys]}``.

Brands are stored with a display ``name``, the folded ``key`` the parser matches
(``domain.product_attributes.fold``), their ``sources`` and the number of stores
whose titles start with them. The output is deterministic (sorted, no timestamps).

Usage:
    uv run python scripts/build_brand_list.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import data_files  # noqa: E402

from inflation_dashboard.domain.product_attributes import fold  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
MIN_STORES = 3
MIN_FIRST_SHARE = 0.6
MIN_BIGRAM_SHARE = 0.8
MIN_BIGRAM_TITLES = 10
# Only a short first word ("la", "dr", "air") is extended: longer ones are whole brands
# whose titles merely share a product type ("Erikli Su", "Fruko Gazoz").
MAX_BIGRAM_FIRST_LEN = 3
# Titles last priced this long before the newest date are not current for title learning.
CURRENT_DAYS = 60
WATSON_PARTITION = "Cosmetics_Watson.json"
EXCLUDED_GROUPS = ("HousesRent_",)
# Brand-column values that are not brands.
JUNK = frozenset({"diger", "markasiz", "genel", "generic", "yok", "nan", "none", "null", "marka", "brand", "other"})
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(fold(text)))


def display_name(spellings: Counter) -> str:
    """The most common spelling, preferring mixed case over ALL CAPS (ties: alphabetical)."""
    ranked = sorted(spellings.items(), key=lambda item: (item[0].isupper(), -item[1], item[0]))
    name = ranked[0][0]
    return name.title() if name.isupper() and len(name) > 3 else name


def load_products(data_dir: Path) -> list[tuple[str, str, str | None, str]]:
    """Every product as ``(store, name, brand, newest date)`` from the JSON partitions."""
    products = []
    for path in sorted((data_dir / "prices_json").glob("*.json")):
        if path.name.startswith(EXCLUDED_GROUPS) or path.name == WATSON_PARTITION:
            continue
        for product in json.loads(path.read_text(encoding="utf-8")).values():
            prices = product.get("prices") or {}
            if prices and product.get("name"):
                products.append((path.stem, product["name"], product.get("brand"), max(prices)))
    return products


def build(data_dir: Path) -> dict:
    """Compute the brand list (see the module docstring)."""
    data_files.join(data_dir)
    products = load_products(data_dir)
    candidates: dict[tuple[str, ...], dict] = defaultdict(lambda: {"spellings": Counter(), "sources": set()})

    # 1. Retailer brand columns, kept when a title carrying the brand starts with it.
    for store, name, brand, _ in products:
        if not brand:
            continue
        key = tokens(brand)
        if not key or " ".join(key) in JUNK or not any(ch.isalpha() for ch in "".join(key)):
            continue
        if tokens(name)[: len(key)] == key:
            candidates[key]["spellings"][brand.strip()] += 1
            candidates[key]["sources"].add("retailer")

    # 2. The Watsons brand list.
    watson = data_dir / "prices_json" / WATSON_PARTITION
    if watson.exists():
        for product in json.loads(watson.read_text(encoding="utf-8")).values():
            category = (product.get("category") or "").strip()
            key = tokens(category)
            if key and category != "Uncategorized" and " ".join(key) not in JUNK:
                candidates[key]["spellings"][category] += 1
                candidates[key]["sources"].add("watsons")

    # 3. Brands learned from current titles.
    newest = max(date.fromisoformat(day) for *_, day in products)
    cutoff = (newest - timedelta(days=CURRENT_DAYS)).isoformat()
    first_stores: dict[str, set[str]] = defaultdict(set)
    first_count: Counter = Counter()
    any_count: Counter = Counter()
    next_count: dict[str, Counter] = defaultdict(Counter)
    bigram_stores: dict[tuple[str, str], set[str]] = defaultdict(set)
    first_spellings: dict[tuple[str, ...], Counter] = defaultdict(Counter)
    for store, name, _, day in products:
        if day < cutoff:
            continue
        words = tokens(name)
        if not words:
            continue
        any_count.update(set(words))
        first = words[0]
        first_stores[first].add(store)
        first_count[first] += 1
        raw_words = name.split()
        if raw_words:
            first_spellings[(first,)][raw_words[0].strip(",.;:-")] += 1
        if len(words) > 1:
            next_count[first][words[1]] += 1
            bigram_stores[(first, words[1])].add(store)
            if len(raw_words) > 1:
                first_spellings[(first, words[1])][" ".join(raw_words[:2]).strip(",.;:-")] += 1
    for first, stores in first_stores.items():
        if len(stores) < MIN_STORES or len(first) < 2 or not first.isalpha():
            continue
        if first_count[first] / any_count[first] < MIN_FIRST_SHARE or first in JUNK:
            continue
        key: tuple[str, ...] = (first,)
        if len(first) <= MAX_BIGRAM_FIRST_LEN and first_count[first] >= MIN_BIGRAM_TITLES:
            second, count = next_count[first].most_common(1)[0]
            if count / first_count[first] >= MIN_BIGRAM_SHARE and len(bigram_stores[(first, second)]) >= MIN_STORES:
                key = (first, second)
        candidates[key]["spellings"].update(first_spellings[key])
        candidates[key]["sources"].add("titles")

    # 4. Reviewed corrections.
    overrides_path = data_dir / "matching" / "brand_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    for name in overrides.get("add", []):
        key = tokens(name)
        candidates[key]["name"] = name
        candidates[key]["sources"].add("override")
    for removed in overrides.get("remove", []):
        candidates.pop(tokens(removed), None)

    # Stores whose titles start with each brand (longest brand first, like the parser).
    store_sets: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for store, name, _, _ in products:
        words = tokens(name)
        for size in range(min(4, len(words)), 0, -1):
            if words[:size] in candidates:
                store_sets[words[:size]].add(store)
                break
    brands = [
        {
            "name": entry.get("name") or display_name(entry["spellings"]),
            "key": " ".join(key),
            "sources": sorted(entry["sources"]),
            "stores": len(store_sets.get(key, ())),
        }
        for key, entry in candidates.items()
    ]
    brands.sort(key=lambda brand: brand["key"])
    return {
        "description": "Brand list for inflation_dashboard.domain.product_attributes; built by scripts/build_brand_list.py.",
        "count": len(brands),
        "brands": brands,
    }


def write(payload: dict, path: Path) -> None:
    """One brand per line: valid JSON and diffable per brand."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "{",
        f'"description": {json.dumps(payload["description"], ensure_ascii=False)},',
        f'"count": {payload["count"]},',
        '"brands": [',
    ]
    for index, brand in enumerate(payload["brands"]):
        sep = "," if index < len(payload["brands"]) - 1 else ""
        lines.append(json.dumps(brand, ensure_ascii=False) + sep)
    lines += ["]", "}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, help="Default: <data-dir>/matching/brands.json")
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    output = args.output or data_dir / "matching" / "brands.json"
    payload = build(data_dir)
    write(payload, output)
    sources = Counter(source for brand in payload["brands"] for source in brand["sources"])
    print(f"Wrote {output}: {payload['count']:,} brands ({', '.join(f'{k} {v:,}' for k, v in sorted(sources.items()))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
