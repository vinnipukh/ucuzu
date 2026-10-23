"""SQLite queries behind the price-comparison catalog (``/api/catalog/*``).

A catalog *item* is every product row that shares one ``products.name_key``
(see ``inflation_dashboard.domain.catalog``); each row is one store's *offer*.
Searches, listings and deals read only current offers (``is_current = 1``) from
retailers outside ``CATALOG_EXCLUDED_GROUPS``. Case prices (``products.is_case_price``,
a whole case where the title describes one item) never count as an item's lowest
price while another offer exists, and never appear as deals. Connections come from
``sqlite_price_repository`` (read-only, one per thread).
"""

from __future__ import annotations

import time
from typing import Any

from inflation_dashboard.adapters.sqlite_price_repository import (
    close_connection,
    get_db_path,
    get_reusable_connection,
)
from inflation_dashboard.domain.catalog import CATALOG_EXCLUDED_GROUPS, search_terms, split_retailer

CATALOG_SORTS = ("relevance", "price_asc", "price_desc", "drop")
MAX_ITEM_OFFERS = 40
# Product rows read per item before grouping them by store (one store can list
# many products under one name, e.g. every repair service for a phone model).
MAX_ITEM_ROWS = 400
# Larger "drops" are almost always scraper or unit errors (a 10x price is a 90%
# "drop"), not discounts.
MAX_DEAL_DROP_PERCENT = 80.0
# History prices below this share of the item's lowest current price are treated
# as scraper errors when picking the lowest price ever seen.
LOWEST_EVER_FLOOR = 0.25

_CACHE_TTL_SECONDS = 300.0
# db path -> (loaded_at, {retailer_key: (retailer, group, store)})
_retailer_cache: dict[str, tuple[float, dict[int, tuple[str, str, str]]]] = {}

_DROP_PERCENT_SQL = "(p.previous_price - p.latest_price) * 100.0 / p.previous_price"


class CatalogSchemaError(RuntimeError):
    """The database was built before the catalog columns existed."""


def clear_catalog_cache() -> None:
    """Forget the cached retailer table (tests and database swaps)."""
    _retailer_cache.clear()


def _retailers(conn: Any) -> dict[int, tuple[str, str, str]]:
    """Return ``{retailer_key: (retailer, group, store)}``, checking the schema once per load."""
    key = str(get_db_path())
    cached = _retailer_cache.get(key)
    now = time.monotonic()
    if cached is not None and now - cached[0] <= _CACHE_TTL_SECONDS:
        return cached[1]
    columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
    if not {"name_key", "previous_price", "price_since", "is_current", "is_store_latest", "is_case_price"} <= columns:
        raise CatalogSchemaError("Database predates the catalog; run scripts/build_database.py")
    table = {
        retailer_key: (name, *split_retailer(name))
        for retailer_key, name in conn.execute("SELECT retailer_key, name FROM retailers")
    }
    _retailer_cache[key] = (now, table)
    return table


def _retailer_keys(table: dict[int, tuple[str, str, str]], group: str | None, store: str | None) -> list[int]:
    """Catalog retailer keys, optionally narrowed to one group and/or store."""
    return [
        key
        for key, (_, g, s) in table.items()
        if g not in CATALOG_EXCLUDED_GROUPS and (group is None or g == group) and (store is None or s == store)
    ]


def _escape_like(term: str) -> str:
    """Escape LIKE wildcards (``%``, ``_``) and the escape character itself."""
    return term.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _offer(row: dict[str, Any], table: dict[int, tuple[str, str, str]]) -> dict[str, Any]:
    """Shape one products row as an offer dict."""
    retailer, group, store = table[row.pop("retailer_key")]
    previous = row.get("previous_price")
    latest = row.get("latest_price")
    drop = (previous - latest) * 100.0 / previous if previous and latest is not None and previous > latest else None
    return {
        "retailer": retailer,
        "group": group,
        "store": store,
        **row,
        "is_current": bool(row.get("is_current")),
        "is_case_price": bool(row.get("is_case_price")),
        "drop_percent": round(drop, 2) if drop is not None else None,
    }


_OFFER_COLUMNS = """
    p.product_key, p.retailer_key, p.product_id, p.product_name, p.name_key, c.name AS category,
    p.latest_price, p.previous_price, p.price_since, p.first_date, p.last_date,
    p.min_price, p.max_price, p.observations_count, p.is_current, p.is_case_price
"""


def list_groups() -> list[dict[str, Any]]:
    """Catalog groups with their stores and current-offer counts, largest first."""
    conn = get_reusable_connection()
    try:
        table = _retailers(conn)
        rows = conn.execute(
            "SELECT retailer_key, sum(is_current), max(last_date) FROM products GROUP BY retailer_key"
        ).fetchall()
    finally:
        close_connection(conn)

    groups: dict[str, dict[str, Any]] = {}
    for retailer_key, current, last_date in rows:
        retailer, group, store = table[retailer_key]
        if group in CATALOG_EXCLUDED_GROUPS or not current:
            continue
        entry = groups.setdefault(group, {"group": group, "offer_count": 0, "last_date": None, "stores": []})
        entry["offer_count"] += current
        entry["last_date"] = max(filter(None, (entry["last_date"], last_date)), default=None)
        entry["stores"].append({"store": store, "retailer": retailer, "offer_count": current, "last_date": last_date})
    for entry in groups.values():
        entry["stores"].sort(key=lambda s: (-s["offer_count"], s["store"]))
    return sorted(groups.values(), key=lambda g: (-g["offer_count"], g["group"]))


def search_items(
    query: str = "",
    group: str | None = None,
    store: str | None = None,
    sort: str = "relevance",
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Search catalog items; return ``(items, total)``.

    Every normalized query term must occur in the item's ``name_key``. Items
    aggregate the current offers of the selected group/store, counting only each
    store's offers on its newest date for the item (``is_store_latest``): lowest and highest
    price (of offers that are not case prices, unless all are), offer and store counts
    and the largest current price drop. Each item names its cheapest offer (``name``,
    ``store``, ``category``; case prices last) and up to three stores. Price sorts put
    items with only case prices last. ``relevance`` ranks by the number of query terms that match whole
    words, then store count, then shorter names.
    """
    order_by = {
        "relevance": "word_hits DESC, store_count DESC, length(p.name_key) ASC, p.name_key",
        "price_asc": "case_only ASC, min_price ASC, p.name_key",
        "price_desc": "case_only ASC, min_price DESC, p.name_key",
        "drop": "max_drop DESC NULLS LAST, store_count DESC, p.name_key",
    }[sort]
    terms = search_terms(query)

    conn = get_reusable_connection()
    try:
        table = _retailers(conn)
        keys = _retailer_keys(table, group, store)
        if not keys:
            return [], 0
        where = [
            f"p.retailer_key IN ({','.join('?' * len(keys))})",
            "p.is_current = 1",
            "p.is_store_latest = 1",
            "p.latest_price > 0",
        ]
        params: list[Any] = list(keys)
        for term in terms:
            where.append("p.name_key LIKE ? ESCAPE '!'")
            params.append(f"%{_escape_like(term)}%")
        where_sql = " AND ".join(where)
        # Whole-word hits rank "süt 1l" above "sütaş krema" for the query "süt".
        word_hits = " + ".join(["(' ' || p.name_key || ' ' LIKE ? ESCAPE '!')"] * len(terms)) or "0"
        rows = conn.execute(
            f"""
            SELECT p.name_key, count(*) AS offer_count, count(DISTINCT p.retailer_key) AS store_count,
                   coalesce(min(CASE WHEN p.is_case_price = 0 THEN p.latest_price END), min(p.latest_price)) AS min_price,
                   coalesce(max(CASE WHEN p.is_case_price = 0 THEN p.latest_price END), max(p.latest_price)) AS max_price,
                   min(p.is_case_price) AS case_only,
                   max(CASE WHEN p.previous_price > p.latest_price THEN {_DROP_PERCENT_SQL} END) AS max_drop,
                   max(p.last_date) AS last_date, max({word_hits}) AS word_hits, count(*) OVER () AS total
            FROM products AS p
            WHERE {where_sql}
            GROUP BY p.name_key
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            (*[f"% {_escape_like(term)} %" for term in terms], *params, limit, offset),
        ).fetchall()
        if not rows:
            return [], 0
        page_keys = [row[0] for row in rows]
        offer_rows = conn.execute(
            f"""
            SELECT p.name_key, p.retailer_key, p.product_name, c.name, p.latest_price
            FROM products AS p JOIN categories AS c ON c.category_key = p.category_key
            WHERE p.name_key IN ({','.join('?' * len(page_keys))})
              AND p.retailer_key IN ({','.join('?' * len(keys))})
              AND p.is_current = 1 AND p.is_store_latest = 1 AND p.latest_price > 0
            ORDER BY p.is_case_price ASC, p.latest_price ASC
            """,
            (*page_keys, *keys),
        ).fetchall()
    finally:
        close_connection(conn)

    cheapest: dict[str, tuple[Any, ...]] = {}
    stores: dict[str, list[str]] = {}
    for key, retailer_key, product_name, category, _ in offer_rows:
        cheapest.setdefault(key, (retailer_key, product_name, category))
        names = stores.setdefault(key, [])
        store_name = table[retailer_key][2]
        if store_name not in names:
            names.append(store_name)

    items = []
    for key, offer_count, store_count, min_price, max_price, _, max_drop, last_date, _, _ in rows:
        retailer_key, product_name, category = cheapest[key]
        _, item_group, item_store = table[retailer_key]
        items.append(
            {
                "key": key,
                "name": product_name,
                "group": item_group,
                "category": category,
                "store": item_store,
                "stores": stores[key][:3],
                "offer_count": offer_count,
                "store_count": store_count,
                "min_price": min_price,
                "max_price": max_price,
                "max_drop_percent": round(max_drop, 2) if max_drop is not None else None,
                "last_date": last_date,
            }
        )
    return items, rows[0][-1]


def _store_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse offers to one per store: the cheapest offer on the store's newest date.

    The store's other offers (other products under the same name, or older ones)
    move into the chosen offer's ``other_offers``, newest first, then cheapest
    first. Offers without a price never win over priced ones.
    """
    by_store: dict[str, list[dict[str, Any]]] = {}
    for offer in offers:
        by_store.setdefault(offer["retailer"], []).append(offer)

    chosen = []
    for store_offers in by_store.values():
        # Stable sorts, least significant key first: price, then date, then priced.
        store_offers.sort(key=lambda o: o["latest_price"] if o["latest_price"] is not None else 0.0)
        store_offers.sort(key=lambda o: o["last_date"] or "", reverse=True)
        store_offers.sort(key=lambda o: o["latest_price"] is None)
        best, *others = store_offers
        best["other_offers"] = others
        chosen.append(best)
    return chosen


def get_item(key: str) -> dict[str, Any] | None:
    """Return one catalog item with one offer per store and its price history, or ``None``.

    Each store shows its latest price: its cheapest offer on its newest date, with
    the store's other offers in ``other_offers`` (see ``_store_offers``). Offers are
    current first, then case prices last, then cheapest first (at most
    ``MAX_ITEM_OFFERS`` stores); each carries ``history`` as ``[[date, price], ...]``.
    ``summary`` covers the current offers (falling back to all offers when none is
    current), leaving out case prices unless every offer is one, and the lowest price
    ever observed for the item among those offers, ignoring prices below
    ``LOWEST_EVER_FLOOR`` of the lowest current price.
    """
    conn = get_reusable_connection()
    try:
        table = _retailers(conn)
        excluded = [k for k, (_, g, _) in table.items() if g in CATALOG_EXCLUDED_GROUPS] or [-1]
        cursor = conn.execute(
            f"""
            SELECT {_OFFER_COLUMNS}
            FROM products AS p JOIN categories AS c ON c.category_key = p.category_key
            WHERE p.name_key = ? AND p.retailer_key NOT IN ({','.join('?' * len(excluded))})
            ORDER BY p.is_current DESC, p.is_case_price ASC, p.latest_price ASC
            LIMIT ?
            """,
            (key, *excluded, MAX_ITEM_ROWS),
        )
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        if not rows:
            return None
        product_keys = {}
        all_offers = []
        for row in rows:
            product_key = row.pop("product_key")
            offer = _offer(row, table)
            product_keys[id(offer)] = product_key
            all_offers.append(offer)
        offers = _store_offers(all_offers)
        offers.sort(key=lambda o: o["latest_price"] if o["latest_price"] is not None else float("inf"))
        offers.sort(key=lambda o: o["is_case_price"])
        offers.sort(key=lambda o: not o["is_current"])
        offers = offers[:MAX_ITEM_OFFERS]

        # Price history only for the offer shown per store.
        history: dict[int, list[list[Any]]] = {product_keys[id(o)]: [] for o in offers}
        for product_key, date, price in conn.execute(
            f"""
            SELECT product_key, date, price FROM observations
            WHERE product_key IN ({','.join('?' * len(history))})
            ORDER BY product_key, date
            """,
            list(history),
        ):
            history[product_key].append([date, price])
    finally:
        close_connection(conn)

    for offer in offers:
        offer["history"] = history[product_keys[id(offer)]]

    ranked = [o for o in offers if not o["is_case_price"]] or offers
    current = [o for o in ranked if o["is_current"] and o["latest_price"]] or [o for o in ranked if o["latest_price"]]
    current_min = min((o["latest_price"] for o in current), default=None)
    floor = current_min * LOWEST_EVER_FLOOR if current_min else 0.0
    lowest_ever = None
    for offer in ranked:
        for date, price in offer["history"]:
            if price and price >= floor and (lowest_ever is None or price < lowest_ever["price"]):
                lowest_ever = {"price": price, "date": date, "store": offer["store"]}
    best = current[0] if current else offers[0]
    return {
        "key": key,
        "name": best["product_name"],
        "group": best["group"],
        "category": best["category"],
        "offers": offers,
        "summary": {
            "offer_count": len(offers),
            "current_offer_count": sum(1 for o in offers if o["is_current"]),
            "store_count": len({o["retailer"] for o in offers}),
            "min_price": current_min,
            "max_price": max((o["latest_price"] for o in current), default=None),
            "lowest_ever": lowest_ever,
            "last_date": max((o["last_date"] for o in offers if o["last_date"]), default=None),
        },
    }


def list_deals(
    group: str | None = None,
    store: str | None = None,
    min_drop: float = 5.0,
    days: int = 30,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Current offers whose latest price change was a drop of at least ``min_drop`` percent.

    Only changes within ``days`` of the offer's last observation count; drops above
    ``MAX_DEAL_DROP_PERCENT`` and case prices are ignored. Largest drop first.
    """
    conn = get_reusable_connection()
    try:
        table = _retailers(conn)
        keys = _retailer_keys(table, group, store)
        if not keys:
            return []
        cursor = conn.execute(
            f"""
            SELECT {_OFFER_COLUMNS}
            FROM products AS p JOIN categories AS c ON c.category_key = p.category_key
            WHERE p.retailer_key IN ({','.join('?' * len(keys))})
              AND p.is_current = 1 AND p.is_case_price = 0 AND p.latest_price > 0
              AND p.previous_price > p.latest_price AND p.price_since >= date(p.last_date, ?)
              AND {_DROP_PERCENT_SQL} BETWEEN ? AND ?
            ORDER BY {_DROP_PERCENT_SQL} DESC, p.observations_count DESC
            LIMIT ?
            """,
            (*keys, f"-{days} days", min_drop, MAX_DEAL_DROP_PERCENT, limit),
        )
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        close_connection(conn)

    deals = []
    for row in rows:
        row.pop("product_key")
        deals.append(_offer(row, table))
    return deals
