"""Title parser and unit price rules (inflation_dashboard.domain.product_attributes).

Every title below is a real scraped title from data/prices_json.
"""

from __future__ import annotations

import pytest

from inflation_dashboard.domain.product_attributes import (
    KIND_CAPACITY,
    KIND_CONTENTS,
    KIND_DIMENSION,
    brand_keys,
    fold,
    parse,
    unit_price,
)

BRANDS = brand_keys(["Pastel", "Piranha", "Pınar", "Sleepy", "Philips", "Air Wick", "Dr. Oetker", "La Lorraine", "Sütaş"])


# title -> (amount, unit, pack, kind)
SIZES = [
    ("Pınar Süt 200 ml", 200, "ml", 1, KIND_CONTENTS),
    ("Pınar Tam Yağlı Süt 1 lt", 1000, "ml", 1, KIND_CONTENTS),
    ("Billur Tuz Rafine İyotlu Sofra Tuzu 1,5 Kg", 1500, "g", 1, KIND_CONTENTS),
    ("Ülker Çikolata Fındık Rüyası 40.5 g", 40.5, "g", 1, KIND_CONTENTS),
    ("Arko Yağlı Krem 20 cc", 20, "ml", 1, KIND_CONTENTS),
    # Turkish thousands separators
    ("Yumoş Extra Manolya Konsantre Yumuşatıcı 1.440 Ml", 1440, "ml", 1, KIND_CONTENTS),
    ("Domestos Çamaşır Suyu Çam Ferahlığı 1,850 ml", 1850, "ml", 1, KIND_CONTENTS),
    # multipacks
    ("Yumoş Extra Orkide 3 x 1.440 Ml", 1440, "ml", 3, KIND_CONTENTS),
    ("Torku Süt Muzlu 6X180 ml 1 Adet", 180, "ml", 6, KIND_CONTENTS),
    ("Raid Max Böceksavar Kokusuz Sprey 300 Ml X 2 Adet", 300, "ml", 2, KIND_CONTENTS),
    ("Avşar Tuzlu Erik Aromalı Gazlı İçecek 200 ml 6'lı", 200, "ml", 6, KIND_CONTENTS),
    ("Coca Cola Kutu 330 ml 24'lü", 330, "ml", 24, KIND_CONTENTS),
    ("Dimes Karışık Meyve Suyu 200 Ml 27 Adet", 200, "ml", 27, KIND_CONTENTS),
    ("Doğuş Demlik Early Grey Demlik Poşet Çay 3,2 g 100 Adet", 3.2, "g", 100, KIND_CONTENTS),
    ("İnişdibi Maden Suyu (6*200) Ml", 200, "ml", 6, KIND_CONTENTS),
    ("Freshmaker Islak Mendil Meyveli 3X15 li", 15, "adet", 3, KIND_CONTENTS),
    # a count before the size, or a large count, is pieces inside: the size is the total
    ("Doğuş Detox Karışık Bitki Çayı 20'li 30G", 30, "g", 1, KIND_CONTENTS),
    ("Mgs Küp Şeker 405 Li 1 Kg", 1000, "g", 1, KIND_CONTENTS),
    ("Bornova Küp Şeker 1000 Gr 405'li", 1000, "g", 1, KIND_CONTENTS),
    # summed and fractional sizes
    ("Aptamil 4 Devam Sütü 800 + 250 gr 3'lü", 1050, "g", 3, KIND_CONTENTS),
    ("Dr. Oetker Çikolata Parçalı/Vanilya Puding 2'li 120 G/115 G", 235, "g", 1, KIND_CONTENTS),
    ("Fındık İçi 1/2 Kg", 500, "g", 1, KIND_CONTENTS),
    # counted goods: TL/adet per piece
    ("Sleepy Natural Double Soft 4 No 7-14 Kg 52'li", 52, "adet", 1, KIND_CONTENTS),
    ("Solo Havlu Kağıt 6'lı", 6, "adet", 1, KIND_CONTENTS),
    ("Fe Tırnak Makası 1 Adet", 1, "adet", 1, KIND_CONTENTS),
    # produce sold per kilogram
    ("Portakal Washington Kg", 1000, "g", 1, KIND_CONTENTS),
    # glued and dotted numbers
    ("Parodontax Beyazlatıcı Diş Macunu75 Ml", 75, "ml", 1, KIND_CONTENTS),
    ("Garnıer Hyaluronik Aloe Yatıştıran Temizleyi.250ml", 250, "ml", 1, KIND_CONTENTS),
    # scraper unit typos
    ("Sütaş Kaymaklı Yoğurt 1750 kg", 1750, "g", 1, KIND_CONTENTS),
    ("Hayat Ulw Su 0.75 ml", 750, "ml", 1, KIND_CONTENTS),
    # capacities: the litres/kilograms belong to the appliance or container
    ("Vestel NF52011 EMS 451 Lt No-Frost Buzdolabı", 451_000, "ml", 1, KIND_CAPACITY),
    ("CLASSIC TARTI Tefal Classic 180 Kg Kapasiteli Tartı - Gri", 180_000, "g", 1, KIND_CAPACITY),
    ("Kiwi KK-3331 Su Isıtıcı Kettle 1,8 Lt", 1800, "ml", 1, KIND_CAPACITY),
    ("Simlife Trend Kapaklı Saklama Kabı 7,5 L", 7500, "ml", 1, KIND_CAPACITY),
    ("Parla Endüstriyel Çöp Torbası Jumbo Boy (80×110 cm | 90 lt) 30 Yaprak", 90_000, "ml", 30, KIND_CAPACITY),
    # ... but consumables for appliances are contents
    ("Pril Bulaşık Makinesi Parlatıcısı 750 Ml", 750, "ml", 1, KIND_CONTENTS),
    ("Hanımdan Fırın Sütlaç 200 G", 200, "g", 1, KIND_CONTENTS),
    ("Ülker Rondo Çilek Kremalı 61 g", 61, "g", 1, KIND_CONTENTS),
    ("Neutrogena Hydro Boost J Kavanoz Vücut Kremi 200 Ml", 200, "ml", 1, KIND_CONTENTS),
    # washes: detergents are priced per wash
    ("Perwoll Geliştirilmiş Siyah Sıvı Çamaşır Deterjanı 50 Yıkama 3 lt", 3000, "ml", 1, KIND_CONTENTS),
]


@pytest.mark.parametrize(("title", "amount", "unit", "pack", "kind"), SIZES)
def test_size(title: str, amount: float, unit: str, pack: int, kind: str) -> None:
    parsed = parse(title)
    assert (parsed.amount, parsed.unit, parsed.pack, parsed.kind) == (pytest.approx(amount), unit, pack, kind)


# Not contents: dimensions, lumens, an "L" that is a shape, weight classes.
NO_SIZE = [
    ("Magic Saver Bag Vakumlu Poşet Tekli 50x70 L", KIND_DIMENSION, "dim=50x70"),
    ("ŞEN 1 Numara 16x25x25 L Gönye (ŞEN-601)", KIND_DIMENSION, "dim=16x25x25"),
    ("Philips Ampül 8 W 720 L Beyaz", None, "lumen=720"),
    ("Çipura 400/600 Kg", None, "range=400-600kg"),
    ("Piranha 7849 Bluetooth Hoparlör", None, None),
]


@pytest.mark.parametrize(("title", "kind", "attr"), NO_SIZE)
def test_no_contents_size(title: str, kind: str | None, attr: str | None) -> None:
    parsed = parse(title)
    assert parsed.amount is None
    assert parsed.kind == kind
    assert unit_price(parsed, 100.0) is None
    if attr:
        assert attr in parsed.attrs


def test_pieces_are_kept_beside_the_size() -> None:
    parsed = parse("Lipton Ekstra Dem Demlik Poşet Çay 100 Lü 320 Gr")
    assert (parsed.amount, parsed.pack, parsed.pieces) == (320, 1, 100)


# Pairs cimri keeps apart: the parsed fields must differ.
MUST_NOT_MERGE = [
    ("Pastel Oje 112", "Pastel Oje No: 380 - Pastel"),
    ("Piranha 7849 Bluetooth Hoparlör", "Piranha Bluetooth Hoparlör 7889"),
    ("Pınar Yarım Yağlı Süt 1 L", "Pınar Tam Yağlı Süt 1 L"),
    ("Pınar Süt 200 ml", "Pınar Süt 1 L"),
    ("Pınar Süt Denge Laktozsuz 200 ml", "Pınar Süt 200 ml"),
    ("Uludağ Gazoz Cam 250 ml", "Uludağ Gazoz 250 ml"),
    ("Sleepy Natural Double Soft 4 No 7-14 Kg 52'li", "Sleepy Natural Double Soft 6 No 15-25 Kg 32'li"),
]


def _identity(title: str) -> tuple:
    p = parse(title, BRANDS)
    return p.brand, frozenset(p.base_tokens), p.attrs, frozenset(p.model_codes), p.amount, p.unit, p.pack


@pytest.mark.parametrize(("a", "b"), MUST_NOT_MERGE)
def test_must_not_merge(a: str, b: str) -> None:
    assert _identity(a) != _identity(b)


def test_same_product_different_wording_parses_alike() -> None:
    assert _identity("Pastel Oje 112") == _identity("PASTEL OJE 112")
    assert _identity("Pınar Tam Yağlı Süt 1 L") == _identity("Pınar Tam Yağlı Süt 1 Lt")
    a, b = parse("Pastel Oje No: 380 - Pastel", BRANDS), parse("Pastel Oje 380", BRANDS)
    assert a.model_codes == b.model_codes == ("380",)


ATTRIBUTES = [
    ("Pınar Yarım Yağlı Süt 1 L", "fat=half"),
    ("Birşah Tam Yağlı Süt 1 L", "fat=full"),
    ("Pınar Süt Denge Laktozsuz 200 ml", "lactose_free"),
    ("Pınar Organik Süt Uht 200 ml", "organic"),
    ("Pınar Organik Süt Uht 200 ml", "uht"),
    ("Uludağ Gazoz Cam 250 ml", "pack=glass"),
    ("Sütaş Ayran %1,5 Yağlı 1 L", "pct=1.5"),
    ("Sleepy Natural Double Soft 4 No 7-14 Kg 52'li", "range=7-14kg"),
]


@pytest.mark.parametrize(("title", "attr"), ATTRIBUTES)
def test_attributes(title: str, attr: str) -> None:
    assert attr in parse(title).attrs


def test_pine_is_not_glass() -> None:
    assert "pack=glass" not in parse("Domestos Çamaşır Suyu Çam Ferahlığı 1,850 ml").attrs


BRAND_CASES = [
    ("Air Wick Freshmatic Yedek 250 ml", "air wick", ("freshmatic", "yedek")),
    ("Dr. Oetker Çikolata Parçalı/Vanilya Puding 2'li 120 G/115 G", "dr oetker", ("cikolata", "parcali", "vanilya", "puding")),
    ("La Lorraine Tam Buğday Ekmeği 300 g", "la lorraine", ("tam", "bugday", "ekmegi")),
    ("SÜTAŞ KAYMAKLI YOĞURT 1750 G", "sutas", ("kaymakli", "yogurt")),
    ("Kırmızı Pancar (Çukundur)", None, ("kirmizi", "pancar", "cukundur")),
]


@pytest.mark.parametrize(("title", "brand", "tokens"), BRAND_CASES)
def test_brand_and_base_tokens(title: str, brand: str | None, tokens: tuple[str, ...]) -> None:
    parsed = parse(title, BRANDS)
    assert parsed.brand == brand
    assert parsed.base_tokens == tokens


def test_brand_hint_from_the_retailer_column() -> None:
    assert parse("Eker Puding Çikolatalı 65 G", brand_hint="Eker").brand == "eker"
    assert parse("Puding Çikolatalı 65 G", brand_hint="Eker").brand is None


UNIT_PRICES = [
    ("Pınar Süt 1 L", 50.0, (0.05, "ml")),
    ("Torku Süt Muzlu 6X180 ml", 108.0, (0.1, "ml")),
    ("Billur Tuz 1,5 Kg", 30.0, (0.02, "g")),
    ("Sleepy Natural Double Soft 4 No 7-14 Kg 52'li", 520.0, (10.0, "adet")),
    ("Perwoll Siyah Sıvı Çamaşır Deterjanı 50 Yıkama 3 lt", 300.0, (6.0, "yikama")),
    ("Bahçe Hortumu 25 m", 500.0, (20.0, "m")),
    ("Laminat Parke 8 mm 2,13 m2", 426.0, (200.0, "m2")),
]


@pytest.mark.parametrize(("title", "price", "expected"), UNIT_PRICES)
def test_unit_price(title: str, price: float, expected: tuple[float, str]) -> None:
    value, unit = unit_price(parse(title), price)
    assert (value, unit) == (pytest.approx(expected[0]), expected[1])


@pytest.mark.parametrize("price", [None, 0.0, -5.0])
def test_unit_price_needs_a_positive_price(price: float | None) -> None:
    assert unit_price(parse("Pınar Süt 1 L"), price) is None


def test_no_unit_price_without_size_or_for_capacity() -> None:
    assert unit_price(parse("Pastel Oje 112"), 100.0) is None
    assert unit_price(parse("Vestel NF52011 EMS 451 Lt No-Frost Buzdolabı"), 30_000.0) is None


def test_fold() -> None:
    assert fold("İSTANBUL Şekerli ÇAY") == "istanbul sekerli cay"
    assert fold("IŞIK") == "isik"
