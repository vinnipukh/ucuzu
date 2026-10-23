"""Rules for scraper prices that must not be shown as real prices.

``scripts/build_database.py`` applies them to every observation before it
summarizes products:

- **Missing prices.** Prices of 0 or less, and *placeholder* prices: the
  ``999`` family (``999``, ``999.9``, ``999.99``, ``9999`` … up to seven nines)
  that some scrapers write when a product has no price. ``999.99 TL`` is also a
  common real price (clothing, home goods), so a family price is a placeholder only
  when a reference price disagrees with it by more than ``PLACEHOLDER_RATIO``: the
  product's own other prices, or else the prices of the same item (same
  ``name_key``) in other stores. Without a reference the price is kept.
- **Thousands written with a dot.** Some stores (``THOUSANDS_DOT_RETAILERS``) store
  1.769 TL for 1,769 TL. A price under 10 is multiplied by 1000 when a reference
  price is close to that (``THOUSANDS_RATIO``); an unconfirmed one with three
  decimals is treated as missing, since real prices at those stores have at most
  two.
- **Case prices.** ``CASE_PRICE_RETAILERS`` sell whole cases (koli) while their
  titles describe one item, and their scrapers garble some prices; their offers
  are flagged so they never rank as an item's cheapest price.

All functions are pure; references are medians of usable prices (``reference_price``).
"""

from __future__ import annotations

from statistics import median
from typing import Iterable

# 999, 999.9, 999.99, 9999, ... 9999999.99
PLACEHOLDER_PRICES = frozenset(
    round(int("9" * nines) + fraction, 2) for nines in range(3, 8) for fraction in (0.0, 0.9, 0.99)
)
# A family price within this factor of the reference is a real price (a sale from
# 1999.99 to 999.99 halves it); outside it the price is a placeholder.
PLACEHOLDER_RATIO = 2.5
THOUSANDS_DOT_RETAILERS = frozenset({"Markets / sehzade"})
# Below this a price at a THOUSANDS_DOT_RETAILERS store may be thousands.
THOUSANDS_DOT_LIMIT = 10.0
# The reference must lie within this factor of price * 1000 to confirm a repair.
THOUSANDS_RATIO = 2.0
CASE_PRICE_RETAILERS = frozenset({"Markets / BizimMarket"})


def is_placeholder_family(price: float) -> bool:
    """True for the 999 family of prices (``999``, ``999.99``, ``9999.9`` ...)."""
    return round(price, 2) in PLACEHOLDER_PRICES


def has_three_decimals(price: float) -> bool:
    """True when the price has a non-zero third decimal (``1.769``)."""
    return round(price * 1000) % 10 != 0


def reference_price(prices: Iterable[float]) -> float | None:
    """Median of the prices that can serve as a reference: positive and not a 999-family price."""
    usable = [price for price in prices if price > 0 and not is_placeholder_family(price)]
    return median(usable) if usable else None


def is_placeholder(price: float, own_reference: float | None, peer_reference: float | None) -> bool:
    """Whether a 999-family ``price`` is a placeholder.

    The product's own reference wins over its peers' (other stores, same item);
    with neither the price is kept as real.
    """
    if not is_placeholder_family(price):
        return False
    reference = own_reference if own_reference is not None else peer_reference
    if reference is None:
        return False
    ratio = price / reference
    return not (1 / PLACEHOLDER_RATIO <= ratio <= PLACEHOLDER_RATIO)


def repair_thousands(price: float, own_reference: float | None, peer_reference: float | None) -> float | None:
    """The corrected price for a dotted-thousands store, or ``None`` when the price is missing.

    Prices of ``THOUSANDS_DOT_LIMIT`` and above come back unchanged. Below it the
    price is multiplied by 1000 when the reference (own first, else peers', both
    from prices of at least ``THOUSANDS_DOT_LIMIT``) confirms it; unconfirmed
    prices with three decimals are missing; others are kept.
    """
    if price >= THOUSANDS_DOT_LIMIT:
        return price
    reference = own_reference if own_reference is not None else peer_reference
    if reference is not None and 1 / THOUSANDS_RATIO <= reference / (price * 1000) <= THOUSANDS_RATIO:
        return round(price * 1000, 2)
    return None if has_three_decimals(price) else price
