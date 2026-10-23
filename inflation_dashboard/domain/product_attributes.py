"""Rule-based product title parser: brand, size, pack, variant attributes and model codes.

``parse`` turns a scraped product title such as ``"Pınar Süt Yarım Yağlı 6x200 ml"``
into a :class:`ParsedName`; ``unit_price`` turns a parsed title and a package price
into a price per unit (TL/ml, TL/g, TL/adet, TL/yıkama, TL/m or TL/m²). The build
stores the unit price on ``products``; later matching phases build product and
family keys from the parsed fields.

Rules (``docs/DATABASE.md`` has the user-facing summary):

* Text is Turkish-lowercased and folded to ASCII (``ı``→``i``, ``ğ``→``g`` …).
* Sizes are ``<number> <unit>`` with ml/cl/l, g/kg, m, m², counted units (adet,
  tablet, rulo …) or washes (``24 yıkama``). Turkish thousands separators are read
  in small units (``1.440 ml``, ``1,850 ml``); ``800 + 250 g`` and ``120 g/115 g``
  are summed. When there are several sizes the last one wins; a wash count beats a
  volume (detergents are priced per wash).
* ``6x200 ml`` / ``200 ml x 6`` and a count *after* the size (``200 ml 6'lı``,
  ``24'lü Koli``) are multipacks (``pack``). A count *before* the size
  (``20'li 30 g`` tea bags) or above ``MAX_PACK`` is the number of pieces inside
  (``pieces``); the size is then the total. A count with no size is the size
  itself in pieces (``Yumurta 30'lu`` → 30 adet).
* Weight/age ranges (``7-14 kg`` diapers), dimensions (``50x70``, ``160 mm``),
  technical specs (W, V, GB, mAh, lümen, mg …) and percentages become ``attrs``,
  never sizes. Capacities (``180 kg kapasiteli``, a fridge's litres, a pot's
  litres) set ``kind`` to ``"capacity"``; lamp titles' ``L`` values are lumens.
* Bare numbers and letter+digit codes left over are ``model_codes`` (shade 112 vs
  380 are different products).

Pure functions; no I/O. The brand list is passed in by the caller
(``data/matching/brands.json`` via :func:`brand_keys`).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

# A count after the size above this is a piece count, not a multipack (küp şeker 1 kg 405'li).
MAX_PACK = 48
# A per-item volume above this in an ``N x <size>`` pattern means it is a dimension (50x70 L bag).
MAX_PACK_ITEM_ML = 30_000

KIND_CONTENTS = "contents"
KIND_CAPACITY = "capacity"
KIND_DIMENSION = "dimension"

# Unit spelling (folded) -> (base unit, factor to base unit).
_UNITS: dict[str, tuple[str, float]] = {
    "ml": ("ml", 1), "mlt": ("ml", 1), "mililitre": ("ml", 1), "cc": ("ml", 1),
    "cl": ("ml", 10),
    "l": ("ml", 1000), "lt": ("ml", 1000), "ltr": ("ml", 1000), "litre": ("ml", 1000), "liter": ("ml", 1000),
    "g": ("g", 1), "gr": ("g", 1), "grm": ("g", 1), "gram": ("g", 1), "gramlik": ("g", 1),
    "kg": ("g", 1000), "kgm": ("g", 1000), "kilo": ("g", 1000), "kilogram": ("g", 1000),
    "m": ("m", 1), "mt": ("m", 1), "mtr": ("m", 1), "metre": ("m", 1),
    "m2": ("m2", 1), "metrekare": ("m2", 1),
    "adet": ("adet", 1), "adt": ("adet", 1), "ad": ("adet", 1), "pcs": ("adet", 1), "tablet": ("adet", 1),
    "kapsul": ("adet", 1), "rulo": ("adet", 1), "poset": ("adet", 1), "yaprak": ("adet", 1),
    "cift": ("adet", 1), "parca": ("adet", 1), "dilim": ("adet", 1), "softgel": ("adet", 1), "sase": ("adet", 1),
    "pastil": ("adet", 1), "efervesan": ("adet", 1),
    "yikama": ("yikama", 1),
}
_UNIT_ALT = "|".join(sorted((re.escape(u) for u in _UNITS), key=len, reverse=True))
_NUM = r"\d+(?:[.,]\d+)?"
# A number not glued to a preceding letter/digit (SY8145L is a model code, not 8145 L).
_LEAD = r"(?<![0-9][.,/])(?<![a-z0-9])"
_TAIL = r"(?![a-z0-9])"
# "800 + 250 g" and "120 g/115 g" are summed; a bare "400/600 kg" is a weight class (_RANGE).
_SIZE = re.compile(
    rf"{_LEAD}(?P<num>{_NUM}(?:\s*(?:{_UNIT_ALT})?\s*\+\s*{_NUM}|\s*(?:{_UNIT_ALT})\s*/\s*{_NUM})*)"
    rf"\s*(?P<unit>{_UNIT_ALT}){_TAIL}"
)
_PACK_BEFORE = re.compile(
    rf"{_LEAD}(?P<pack>\d{{1,3}})\s*[x*]\s*(?P<num>{_NUM})\s*\)?\s*(?P<unit>{_UNIT_ALT}){_TAIL}"
)
_PACK_AFTER = re.compile(
    rf"{_LEAD}(?P<num>{_NUM})\s*(?P<unit>{_UNIT_ALT})\s*[x*]\s*(?P<pack>\d{{1,3}})(?![\d.,])(?:\s*(?:adet|li|lu)\b)?"
)
_PACK_COUNT = re.compile(r"(?<![a-z0-9.,])(?P<pack>\d{1,2})\s*[x*]\s*(?P<n>\d{1,4})\s*'?\s*(?:li|lu)(?![a-z])")
# "Macunu75 ml": a number glued to a word, then a space and a unit.
_GLUED = re.compile(r"(?<=[a-z]{4})(?=\d+(?:[.,]\d+)?\s+(?:ml|gr|g|kg|lt|l|cl|adet)\b)")
_COUNT = re.compile(r"(?<![0-9][.,])(?<![a-z0-9])(?P<n>\d{1,4})\s*'?\s*(?:li|lu|lik|luk)(?![a-z])(?:\s*(?:paket|koli|set)\b)?")
_BARE_KG = re.compile(r"(?<![\d.,]\s)(?<![\d.,])\b(?:kg|kilo)\b(?!\s*\d)")
_BARE_ADET = re.compile(r"(?<![\d.,]\s)(?<![\d.,])\badet\b")
_ONE_ADET = re.compile(r"(?<![\d.,])\b1\s*(?:adet|ad)\b")
_FRACTION = re.compile(r"(?<![\d.,])1\s*/\s*([24])(?=\s*(?:kg|kilo|lt|l|litre)\b)")
_CASE_NOTE = re.compile(r"\(\s*1\s*/\s*\d+\s*\)")
_PERCENT = re.compile(rf"%\s*(?P<a>{_NUM})|(?P<b>{_NUM})\s*%")
_RANGE = re.compile(
    rf"{_LEAD}(?P<a>{_NUM})\s*(?:-|/(?=\s*\d{{2}}))\s*(?P<b>{_NUM})\s*"
    r"(?P<unit>kg|gr|g|ay|yas|cm|mm|mt|m|kisilik|kisi|lt|l|ml|w|v|numara|no|beden)?(?![a-z0-9])"
)
_DIMENSION = re.compile(
    rf"{_LEAD}(?P<dim>{_NUM}(?:\s*(?:cm|mm|m)?\s*[x*]\s*{_NUM}){{1,2}})\s*(?P<unit>cm|mm|mt|m|metre)?{_TAIL}"
)
_SPEC_UNITS = (
    "w|watt|kw|kwh|v|volt|mah|gb|tb|mb|hz|ghz|mhz|inc|inch|inç|mm|cm|lumen|lm|btu|dpi|mp|rpm|devir|bar|"
    "mg|mcg|iu|kcal|cal|kalori|ay|yas|yasa|derece|piksel|core|cekirdek|kat|kademe|sn|dk|saat|"
    "gun|hafta|kisilik|kisi|parcali"
)
_SPEC = re.compile(rf"{_LEAD}(?P<num>{_NUM})\s*(?P<unit>{_SPEC_UNITS}){_TAIL}")
_INCH = re.compile(rf"{_LEAD}(?P<num>{_NUM})\s*(?:\"|''|”|“)")
_CAPACITY_WORD = re.compile(rf"(?P<num>{_NUM})\s*(?P<unit>{_UNIT_ALT})\s*(?:lik\s*|luk\s*)?kapasite")
_TOKEN = re.compile(r"[a-z0-9]+")


def _words(*words: str) -> re.Pattern[str]:
    """Whole words (folded), allowing a Turkish possessive/plural suffix (``tencere`` / ``tenceresi``)."""
    return re.compile(r"\b(?:" + "|".join(words) + r")(?:i|u|si|su|leri|lari)?\b")


# Products whose litres/kilograms describe the appliance ...
_APPLIANCE = _words(
    "buzdolab", "derin dondurucu", "dondurucu", "camasir makinesi", "camasir makinasi",
    "kurutma makinesi", "bulasik makinesi", "firin", "mikrodalga", "airfryer", "air fryer", "fritoz",
    "tarti", "baskul", "kettle", "su isitici", "supurge", "nem alma cihaz", "klima", "sofben",
    "termosifon", "kombi", "sebil", "blender", "mutfak robotu", "mikser", "dograyici",
    "cay makinesi", "kahve makinesi", "multicooker", "vantilator", "isitici", "valiz", "canta", "bavul",
)
# ... and containers whose litres are their volume (a mass on them is still contents: "kavanoz bal 450 g").
_CONTAINER = _words(
    "tencere", "tava", "termos", "matara", "suluk", "bardag", "bardak seti", "fincan", "kavanoz",
    "saklama kab", "saklama kutu", "kap", "kab", "kova", "surahi", "sise seti", "depo",
    "cop kova", "cop kutu", "sepet", "duduklu", "caydanlik", "cezve", "karaf", "buzluk", "beslenme",
    "sirt canta", "mama kab", "kase", "kupa bardak",
)
# ... unless the title is a consumable for them (dishwasher tablets, fridge bags, oven-baked rice pudding).
_CONSUMABLE = re.compile(
    r"\b(?:tablet|kapsul|deterjan|parlatic|temizle|tuz|poset|torba|sabun|krem|jel|losyon|sampuan|yumusatic|"
    r"kirec|sivi|sut|sutlac|misir|makarna|patates|tavuk|kofte|ekmek|borek|kek|sos|mama|kahve|cay|bal|"
    r"zeytin|recel|peynir|yogurt|tursu|koku|sprey|filtre|yedek|toz|pizza|yufka|corba|suyu)"
)
_ALWAYS_CAPACITY = _words("cop torba", "cop poset", "cop kova", "cop kutu", "cop sepet")
_LAMP = _words("ampul", "led", "lamba", "spot", "armatur", "aydinlatma", "projektor", "fener", "avize", "aplik")

# Variant attributes (cimri: different products). Matched on the folded text.
_ATTRIBUTE_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), label)
    for pattern, label in (
        (r"\btam\s*yagli\b", "fat=full"),
        (r"\b(?:yarim|y)\s*\.?\s*yagli\b", "fat=half"),
        (r"\baz\s*yagli\b", "fat=low"),
        (r"\byagsiz\b", "fat=none"),
        (r"\blaktozsuz\b", "lactose_free"),
        (r"\bsekersiz\b", "sugar_free"),
        (r"\bglutensiz\b", "gluten_free"),
        (r"\btuzsuz\b", "salt_free"),
        (r"\bkafeinsiz\b", "decaf"),
        (r"\bilave\s*sekersiz\b", "no_added_sugar"),
        (r"\bdiyet\b|\bdiet\b|\blight\b|\bzero\b", "light"),
        (r"\borganik\b", "organic"),
        (r"\buht\b", "uht"),
        (r"\bpastorize\b", "pasteurised"),
        (r"\bpet\s*sise\b|\bpet\b", "pack=pet"),
        (r"\bteneke\b|\bkutu\s*icecek\b", "pack=can"),
        (r"\bkarton\s*kutu\b|\btetra\s*pak\b", "pack=carton"),
    )
)
_GLASS = re.compile(r"(?<![\wçğıöşü])cam(?![\wçğıöşü])")
_NOISE_PHRASES = re.compile(
    r"\b(?:ithalatci|distributor|resmi\s+distributor|turkiye|uretici)\s+garantili\b|\bgarantili\b|"
    r"\byeni\s+urun\b|\bfirsat\s+urunu\b|\bkampanyali\b|\bavantajli\b|\bsuper\s+fiyat\b|\bekonomik\s+boy\b"
)
_STOPWORDS = frozenset({
    "adet", "ad", "ve", "ile", "no", "numara", "num", "nr", "kapasiteli", "kapasite", "li", "lu", "lik", "luk",
    "x", "paket", "pk", "koli", "cesitleri", "cesit", "the", "of", "and", "ml", "gr", "g", "kg", "lt", "l", "cl",
})
_PREFIX_NOISE = frozenset({"yeni", "urun", "kampanya", "firsat", "indirimli"})

_FOLD = str.maketrans({
    "ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c", "â": "a", "î": "i", "û": "u",
    "’": "'", "‘": "'", "`": "'", "´": "'", "×": "x", "²": "2",
})


@dataclass(frozen=True)
class ParsedName:
    """What a product title says, in folded (ASCII, lowercase) form.

    ``amount`` is per item in ``unit`` (``ml``, ``g``, ``m``, ``m2``, ``adet`` or
    ``yikama``); the package holds ``pack`` items. ``pieces`` is a piece count the
    title states besides the size (20 tea bags in 30 g). ``kind`` says whether the
    size is the contents (unit price applies), a capacity or only dimensions.
    """

    brand: str | None
    base_tokens: tuple[str, ...]
    amount: float | None
    unit: str | None
    pack: int = 1
    pieces: int | None = None
    attrs: frozenset[str] = field(default_factory=frozenset)
    model_codes: tuple[str, ...] = ()
    kind: str | None = None

    @property
    def total_amount(self) -> float | None:
        """Contents of the whole package in ``unit`` (``amount * pack``), or ``None``."""
        return None if self.amount is None else self.amount * self.pack


def fold(text: str) -> str:
    """Turkish-aware lowercase folded to ASCII (``İSTANBUL Şeker`` -> ``istanbul seker``)."""
    text = unicodedata.normalize("NFC", str(text)).replace("İ", "i").replace("I", "ı").lower().translate(_FOLD)
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def brand_keys(names: Iterable[str]) -> frozenset[tuple[str, ...]]:
    """Brand names as folded token tuples, the form :func:`parse` matches against."""
    return frozenset(tokens for tokens in (tuple(_TOKEN.findall(fold(name))) for name in names) if tokens)


def _number(text: str, unit: str) -> float | None:
    """Read one number; ``1.440`` / ``1,850`` are thousands in small units (ml, g, adet, yıkama)."""
    base, factor = _UNITS[unit]
    if factor == 1 and base in {"ml", "g", "adet", "yikama"} and re.fullmatch(r"[1-9]\d{0,2}[.,]\d{3}", text):
        return float(text.replace(".", "").replace(",", ""))
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _amount(raw: str, unit: str) -> tuple[str, float] | None:
    """``"800 + 250"`` / ``"120 g/115"`` with ``unit`` -> (base unit, summed amount in base units)."""
    base, factor = _UNITS[unit]
    total = 0.0
    for part in re.split(r"[+/]", raw):
        part = re.sub(rf"\s*(?:{_UNIT_ALT})\s*$", "", part.strip())
        value = _number(part.strip(), unit)
        if value is None:
            return None
        total += value
    return (base, total * factor) if total > 0 else None


def _cut(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _short(value: float) -> str:
    return f"{value:g}"


def parse(name: str, brands: frozenset[tuple[str, ...]] = frozenset(), brand_hint: str | None = None) -> ParsedName:
    """Parse one product title (see the module docstring for the rules).

    ``brands`` are folded token tuples (:func:`brand_keys`); the longest one the
    title starts with is the brand. ``brand_hint`` (the retailer's own brand column)
    is used first when the title starts with it.
    """
    text = fold(name)
    attrs: set[str] = set()
    if _GLASS.search(name.replace("İ", "i").replace("I", "ı").lower()):
        attrs.add("pack=glass")  # before folding: "çam" (pine) is not "cam" (glass)
    text = _GLUED.sub(" ", _CASE_NOTE.sub(" ", text))
    text = _FRACTION.sub(lambda match: "0.5" if match[1] == "2" else "0.25", text)  # 1/2 kg
    text = _NOISE_PHRASES.sub(" ", text)

    for match in _PERCENT.finditer(text):
        attrs.add(f"pct={_short(float((match['a'] or match['b']).replace(',', '.')))}")
    text = _PERCENT.sub(" ", text)

    capacity = bool(_CAPACITY_WORD.search(text))
    for match in reversed(list(_RANGE.finditer(text))):
        unit = match["unit"] or ""
        attrs.add(f"range={match['a']}-{match['b']}{unit}".replace(",", "."))
        text = _cut(text, match.start(), match.end())

    # Explicit multipacks first (6x200 ml), so the dimension rule does not eat them.
    amount = unit = None
    pack = 1
    pack_span: tuple[int, int] | None = None
    for regex in (_PACK_BEFORE, _PACK_AFTER):
        for match in regex.finditer(text):
            sized = _amount(match["num"], match["unit"])
            count = int(match["pack"])
            if sized is None or not 1 < count <= 100:
                continue
            if sized[0] == "ml" and sized[1] > MAX_PACK_ITEM_ML:
                continue
            unit, amount, pack, pack_span = sized[0], sized[1], count, (match.start(), match.end())
        if pack_span:
            break
    if not pack_span and (match := _PACK_COUNT.search(text)):
        unit, amount, pack, pack_span = "adet", float(match["n"]), int(match["pack"]), (match.start(), match.end())
    if pack_span:
        text = _cut(text, *pack_span)

    for match in reversed(list(_DIMENSION.finditer(text))):
        attrs.add("dim=" + re.sub(r"\s+", "", match["dim"]).replace("*", "x").replace(",", ".") + (match["unit"] or ""))
        text = _cut(text, match.start(), match.end())
    for regex in (_SPEC, _INCH):
        for match in reversed(list(regex.finditer(text))):
            unit_name = match.groupdict().get("unit") or "inch"
            attrs.add(f"{re.sub(r'[^a-z]', '', unit_name)}={_short(float(match['num'].replace(',', '.')))}")
            text = _cut(text, match.start(), match.end())

    one_piece = bool(_ONE_ADET.search(text))
    text = _ONE_ADET.sub(" ", text)
    washes = pieces = None
    big_unit = False
    size_start = pack_span[0] if pack_span else None
    counts: list[tuple[int, int]] = []  # (count, position) from "N adet" and "N'li"
    if amount is None:
        sizes = [(sized, match) for match in _SIZE.finditer(text) if (sized := _amount(match["num"], match["unit"]))]
        wash = [item for item in sizes if item[0][0] == "yikama"]
        measured = [item for item in sizes if item[0][0] in {"ml", "g"}]
        other = [item for item in sizes if item[0][0] in {"m2", "m"}]
        if wash:
            washes = int(wash[-1][0][1])
        chosen = (measured or other or [None])[-1]
        if chosen is not None:
            (unit, amount), match = chosen
            big_unit = _UNITS[match["unit"]][1] == 1000
            size_start = match.start()
        counts += [(int(sized[1]), match.start()) for sized, match in sizes if sized[0] == "adet"]
        for _, match in sizes:
            text = _cut(text, match.start(), match.end())
    for match in _COUNT.finditer(text):
        counts.append((int(match["n"]), match.start()))
        text = _cut(text, match.start(), match.end())
    for count, position in sorted(counts, key=lambda item: item[1]):
        if count <= 1 or (pack_span and count == pack):
            continue
        if amount is None:
            unit, amount = "adet", float(count)
        elif unit in {"adet", "m", "m2"}:
            pieces = pieces or count
        elif size_start is not None and position > size_start and pack == 1 and (count <= MAX_PACK or amount <= 10):
            pack = count  # 200 ml 6'lı, 3,2 g 100 adet tea bags
        else:
            pieces = pieces or count  # 20'li 30 g: the size is the total
    if amount is None:
        if _BARE_KG.search(text):
            unit, amount = "g", 1000.0
        elif one_piece or _BARE_ADET.search(text):
            unit, amount = "adet", 1.0

    kind = None
    if amount is not None or washes:
        kind = KIND_CONTENTS
        consumable = unit not in {"ml", "g"} or _CONSUMABLE.search(text)
        if (capacity or _ALWAYS_CAPACITY.search(text)) and unit in {"ml", "g"}:
            kind = KIND_CAPACITY
        elif consumable:
            pass
        elif _APPLIANCE.search(text) or (unit == "ml" and _CONTAINER.search(text)):
            kind = KIND_CAPACITY
        elif unit == "ml" and _LAMP.search(text):
            attrs.add(f"lumen={_short((amount or 0) / 1000)}")  # "720 L" on a bulb is 720 lumens
            amount = unit = None
            pack = 1
            kind = None
    elif any(a.startswith("dim=") for a in attrs):
        kind = KIND_DIMENSION
    if kind == KIND_CONTENTS and amount is not None and unit in {"ml", "g"}:
        if big_unit and amount >= 100_000:
            amount /= 1000  # "Yoğurt 1750 kg", "Deterjan 1500 lt": the scraper meant g/ml
        elif unit == "ml" and amount < 1:
            amount *= 1000  # "Su 0.75 ml"
    if washes:
        attrs.add(f"washes={washes}")

    for regex, label in _ATTRIBUTE_RULES:
        if regex.search(text):
            attrs.add(label)
            text = regex.sub(" ", text)

    tokens = _TOKEN.findall(text)
    start = 0
    while start < len(tokens) - 1 and tokens[start] in _PREFIX_NOISE:
        start += 1
    hint = tuple(_TOKEN.findall(fold(brand_hint))) if brand_hint else ()
    candidates = [hint] if hint else []
    candidates += [c for size in range(4, 0, -1) if (c := tuple(tokens[start:start + size])) in brands]
    brand = None
    for candidate in candidates:
        if tuple(tokens[start:start + len(candidate)]) == candidate:
            brand = " ".join(candidate)
            tokens = tokens[:start] + tokens[start + len(candidate):]
            break
    model_codes = tuple(token for token in tokens if any(ch.isdigit() for ch in token))
    base = tuple(
        token for token in tokens
        if not any(ch.isdigit() for ch in token) and token not in _STOPWORDS and token not in _PREFIX_NOISE
    )
    return ParsedName(
        brand=brand,
        base_tokens=base,
        amount=amount,
        unit=unit if amount is not None else ("yikama" if washes else None),
        pack=pack,
        pieces=pieces,
        attrs=frozenset(attrs),
        model_codes=model_codes,
        kind=kind,
    )


def unit_price(parsed: ParsedName, price: float | None) -> tuple[float, str] | None:
    """Price per unit for a package ``price``: ``(value, unit)`` or ``None``.

    Units: TL/``yikama`` when the title gives washes, otherwise TL per ``ml``,
    ``g``, ``m``, ``m2`` or ``adet`` of the whole package. ``None`` when the price
    is missing or not positive, the title has no contents size, or the size is a
    capacity/dimension.
    """
    if price is None or not price > 0 or parsed.kind != KIND_CONTENTS:
        return None
    washes = next((int(a.split("=", 1)[1]) for a in parsed.attrs if a.startswith("washes=")), None)
    if washes:
        return price / washes, "yikama"
    total = parsed.total_amount
    if not total or parsed.unit is None:
        return None
    return price / total, parsed.unit
