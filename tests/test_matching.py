"""Match keys, family keys, overrides and permanent IDs (inflation_dashboard.domain.matching).

Titles are real scraped titles from data/prices_json.
"""

from __future__ import annotations

import pytest

from inflation_dashboard.domain.matching import Overrides, assign_ids, family_key, match_key, store_key
from inflation_dashboard.domain.product_attributes import brand_keys, parse

BRANDS = brand_keys(["Pastel", "Pınar", "Pantene", "Dr. Oetker", "Coca Cola", "Duru", "Sleepy"])


def key(title: str) -> str | None:
    return match_key(parse(title, BRANDS))


# Different stores' spellings of one product: case, word order, units, "1 Adet", warranty words.
SAME_PRODUCT = [
    ("Dr. Oetker Krem Karamel 92 gr", "Dr.Oetker Krem Karamel 92 g"),
    ("Pantene Onarıcı&Koruyucu Şampuan 625 ml", "Pantene Şampuan Onarıcı Ve Koruyucu 625 ml 1 Adet"),
    ("Pınar Tam Yağlı Süt 1 L", "PINAR SÜT TAM YAĞLI 1000 ML"),
    ("Pastel Oje No: 380 - Pastel", "Pastel Oje 380"),
    ("Duru Pilavlık Bulgur 1 Kg", "Duru Bulgur Pilavlık 1 kg Yeni Ürün"),
    ("Philips Saç Kurutma Makinesi İthalatçı Garantili", "Philips Saç Kurutma Makinesi"),
]


@pytest.mark.parametrize(("a", "b"), SAME_PRODUCT)
def test_same_product_same_key(a: str, b: str) -> None:
    assert key(a) == key(b) is not None


# cimri keeps these apart: size, shade/model code, fat, lactose-free, glass, zero vs light, diaper size.
DIFFERENT_PRODUCTS = [
    ("Pınar Süt 200 ml", "Pınar Süt 1 L"),
    ("Pastel Oje 112", "Pastel Oje 380"),
    ("Pınar Yarım Yağlı Süt 1 L", "Pınar Tam Yağlı Süt 1 L"),
    ("Pınar Süt Denge Laktozsuz 200 ml", "Pınar Süt 200 ml"),
    ("Uludağ Gazoz Cam 250 ml", "Uludağ Gazoz 250 ml"),
    ("Coca Cola Zero 1 L", "Coca Cola Light 1 L"),
    ("Sleepy Natural Double Soft 4 No 7-14 Kg 52'li", "Sleepy Natural Double Soft 5 No 11-18 Kg 52'li"),
    ("Doğuş Detox Bitki Çayı 20'li 30G", "Doğuş Detox Bitki Çayı 30G"),
]


@pytest.mark.parametrize(("a", "b"), DIFFERENT_PRODUCTS)
def test_different_products_different_keys(a: str, b: str) -> None:
    assert key(a) != key(b)


def test_multipacks_share_the_single_items_key() -> None:
    single, six = parse("Pınar Süt 1 L", BRANDS), parse("Pınar Süt 6x1 L", BRANDS)
    assert match_key(single) == match_key(six)
    assert (single.pack, six.pack) == (1, 6)
    assert parse("Jacobs Monarch Gold 30lu 2gr Kahve x 2 Paket").pack == 2


def test_family_key_drops_the_size() -> None:
    sizes = ["Duru Pilavlık Bulgur 500 g", "Duru Pilavlık Bulgur 1 Kg", "Duru Pilavlık Bulgur 2,5 kg"]
    assert len({key(title) for title in sizes}) == 3
    assert len({family_key(parse(title, BRANDS)) for title in sizes}) == 1
    assert family_key(parse("Duru Pilavlık Bulgur 1 Kg", BRANDS)) != family_key(parse("Duru Köftelik Bulgur 1 Kg", BRANDS))
    washes = [parse(f"Ace Sıvı Deterjan {n} Yıkama") for n in (30, 50)]
    assert match_key(washes[0]) != match_key(washes[1])
    assert family_key(washes[0]) == family_key(washes[1])


def test_titles_without_words_have_no_key() -> None:
    assert key("500 g") is None
    assert family_key(parse("1 Adet")) is None
    assert store_key("Markets / A101", "123") == "store|Markets / A101|123"


def test_overrides_split_then_merge() -> None:
    overrides = Overrides.from_json(
        {
            "merge": [{"into": "a", "keys": ["b", "c"], "reason": "same product"}],
            "split": [
                {"retailer": "Markets / X", "product_id": "1"},
                {"retailer": "Markets / X", "product_id": "2", "into": "c"},
            ],
        }
    )
    assert overrides.apply("Markets / Y", "9", "b") == "a"
    assert overrides.apply("Markets / Y", "9", "z") == "z"
    assert overrides.apply("Markets / X", "1", "a") == "store|Markets / X|1"
    assert overrides.apply("Markets / X", "2", "z") == "a"  # moved to c, which merges into a
    # A merge cycle stops instead of looping.
    cycle = Overrides.from_json({"merge": [{"into": "a", "keys": ["b"]}, {"into": "b", "keys": ["a"]}]})
    assert cycle.apply("S", "1", "a") in {"a", "b"}


def test_assign_ids_numbers_new_keys_in_order_and_keeps_old_ones() -> None:
    new, next_id = assign_ids({"b": 7}, ["c", "b", "a"], 10)
    assert (new, next_id) == ({"a": 10, "c": 11}, 12)
    assert assign_ids({"b": 7}, ["b"], 10) == ({}, 10)
