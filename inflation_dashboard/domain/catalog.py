"""Price-comparison catalog rules: product name keys and retailer groups.

Products are stored per retailer with no shared identifier. The catalog treats
two products as the same item when their normalized names (``name_key``) are
equal, so one item can be compared across stores. ``scripts/build_database.py``
stores the key in ``products.name_key``; the API normalizes search text with the
same function so queries match the stored keys.
"""

from __future__ import annotations

import re

# Retailer groups left out of the shopping catalog: their "products" are rental
# listings by district, not goods that stores sell.
CATALOG_EXCLUDED_GROUPS = ("HousesRent",)

_TURKISH_CASEFOLD = str.maketrans({"I": "ı", "İ": "i"})
_DECIMAL_COMMA = re.compile(r"(\d),(\d)")
_NON_WORD = re.compile(r"[^\w.]+")
_STRAY_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_UNIT_GAP = re.compile(r"(\d)\s+(gr|g|kg|ml|cl|l|lt|adet|li|lı|lu|lü)\b")


def name_key(name: str) -> str:
    """Return the comparison key for a product name.

    Turkish-aware lowercase (``I`` -> ``ı``, ``İ`` -> ``i``), decimal commas become
    dots, punctuation becomes spaces, a number and its unit are joined
    (``500 g`` -> ``500g``) and whitespace is collapsed.
    """
    text = name.translate(_TURKISH_CASEFOLD).lower()
    text = _DECIMAL_COMMA.sub(r"\1.\2", text)
    text = _NON_WORD.sub(" ", text)
    text = _STRAY_DOT.sub(" ", text)
    text = _UNIT_GAP.sub(r"\1\2", text)
    return " ".join(text.split())


def search_terms(query: str) -> list[str]:
    """Split search text into normalized terms that must all occur in a ``name_key``."""
    return name_key(query).split()


def split_retailer(retailer: str) -> tuple[str, str]:
    """Split a retailer label into ``(group, store)``.

    ``"Markets / Migros"`` -> ``("Markets", "Migros")``; a label without a store
    part (``"EpeyKatfg"``) is its own group and store.
    """
    group, sep, store = retailer.partition(" / ")
    return (group, store) if sep else (retailer, retailer)
