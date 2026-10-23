"""Product matching: which store products are the same product, and their permanent IDs.

Two store products are one catalog product when their **match key** is equal. The
key is built from the parsed title (:mod:`.product_attributes`) following cimri's
rules: brand, the remaining words (any order, any case), model/shade codes,
variant attributes (fat %, lactose-free, organic, glass vs carton, …) and the size
per item all count; warranty and marketing words, word order and case do not. A
multipack of the same item (6 × 1 L) has the same match key as the single item and
becomes one of its **pack options** (``ParsedName.pack``). The **family key** is the
match key without the size: one brand's osmancık bulgur in 500 g and 1 kg is one
family.

Products and families get permanent numeric IDs from ``data/matching/ids.json``
(:func:`assign_ids`; new keys get the next unused number in key order, old numbers
are never reused). Manual corrections in ``data/matching/overrides.json``
(:class:`Overrides`) are applied after the keys are built. Pure functions; the
build (``scripts/build_database.py``) and ``scripts/assign_ids.py`` do the I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from inflation_dashboard.domain.product_attributes import ParsedName

# Words that never tell two products apart (warranty phrases are removed by the parser).
KEY_NOISE = frozenset({
    "yeni", "firsat", "kampanya", "kampanyali", "indirim", "indirimli", "avantaj", "avantajli", "promosyon",
    "orijinal", "original", "urun", "urunu",
})
# Attributes that are a size, not a variant: they stay in the match key but not in the family key.
_SIZE_ATTRS = ("washes=",)
FIELD_SEPARATOR = "|"


def _identity(parsed: ParsedName, family: bool) -> tuple[str, str, str, str] | None:
    """(brand, words, model codes, attributes) or ``None`` when the title says nothing usable."""
    brand = parsed.brand or ""
    brand_tokens = set(brand.split())
    words = sorted({t for t in parsed.base_tokens if t not in KEY_NOISE and t not in brand_tokens})
    codes = sorted(set(parsed.model_codes))
    if not (brand or words or codes):
        return None
    attrs = sorted(a for a in parsed.attrs if not (family and a.startswith(_SIZE_ATTRS)))
    return brand, " ".join(words), " ".join(codes), ",".join(attrs)


def size_label(parsed: ParsedName) -> str:
    """Size per item in base units for the match key: ``1000ml``, ``52adet``, ``30g/20`` (20 pieces), or ``""``."""
    if parsed.amount is None:
        return ""
    label = f"{parsed.amount:g}{parsed.unit}"
    return f"{label}/{parsed.pieces}" if parsed.pieces else label


def match_key(parsed: ParsedName) -> str | None:
    """``brand|words|codes|attrs|size``; ``None`` when the title has no brand, word or code."""
    identity = _identity(parsed, family=False)
    return None if identity is None else FIELD_SEPARATOR.join((*identity, size_label(parsed)))


def family_key(parsed: ParsedName) -> str | None:
    """``brand|words|codes|attrs`` without the size (and without wash counts); ``None`` like :func:`match_key`."""
    identity = _identity(parsed, family=True)
    return None if identity is None else FIELD_SEPARATOR.join(identity)


def store_key(retailer: str, product_id: str) -> str:
    """Match key for a product that is only itself (no usable title, or split off by an override)."""
    return FIELD_SEPARATOR.join(("store", retailer, product_id))


@dataclass(frozen=True)
class Overrides:
    """Manual matching corrections (``data/matching/overrides.json``), applied after the keys are built.

    ``merges`` maps a match key onto the key it joins; ``splits`` maps one store
    product ``(retailer, product_id)`` to the key it moves to (its own
    :func:`store_key` unless the file names one). Splits run first, then merges.
    """

    merges: Mapping[str, str] = field(default_factory=dict)
    splits: Mapping[tuple[str, str], str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Overrides:
        """Read the ``merge`` and ``split`` lists of an overrides file (see ``docs/DATA_CONTRACT.md``)."""
        merges: dict[str, str] = {}
        for entry in payload.get("merge", []):
            for key in entry["keys"]:
                if key != entry["into"]:
                    merges[key] = entry["into"]
        splits = {
            (entry["retailer"], str(entry["product_id"])): entry.get("into")
            or store_key(entry["retailer"], str(entry["product_id"]))
            for entry in payload.get("split", [])
        }
        return cls(merges, splits)

    def apply(self, retailer: str, product_id: str, key: str) -> str:
        """The final match key of one store product."""
        key = self.splits.get((retailer, product_id), key)
        seen = {key}
        while key in self.merges and self.merges[key] not in seen:
            key = self.merges[key]
            seen.add(key)
        return key


def assign_ids(known: Mapping[str, int], keys: Iterable[str], next_id: int) -> tuple[dict[str, int], int]:
    """IDs for ``keys`` missing from ``known``: ``({key: id}, next unused id)``.

    New keys are numbered from ``next_id`` in sorted key order, so the same inputs
    always give the same IDs (the build's provisional IDs equal the ones
    ``scripts/assign_ids.py`` later commits).
    """
    new: dict[str, int] = {}
    for key in sorted(set(keys) - set(known)):
        new[key] = next_id
        next_id += 1
    return new, next_id
