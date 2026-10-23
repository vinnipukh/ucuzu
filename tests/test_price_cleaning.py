from __future__ import annotations

import pytest

from inflation_dashboard.domain.price_cleaning import (
    has_three_decimals,
    is_placeholder,
    is_placeholder_family,
    reference_price,
    repair_thousands,
)


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (999, True),
        (999.9, True),
        (999.99, True),
        (9999, True),
        (9999.99, True),
        (99999, True),
        (9999999.99, True),
        (99.99, False),
        (998.99, False),
        (1999.99, False),
        (999.95, False),
    ],
)
def test_is_placeholder_family(price: float, expected: bool) -> None:
    assert is_placeholder_family(price) is expected


def test_reference_price_ignores_placeholders_and_non_positive_prices() -> None:
    assert reference_price([100, 120, 9999, 0, -5]) == 110
    assert reference_price([999.99, 0]) is None


@pytest.mark.parametrize(
    ("price", "own", "peer", "expected"),
    [
        # EnglishHome: 9999.99 while the bathrobe costs 1999.99 on other days.
        (9999.99, 1999.99, None, True),
        # CarrefourSA: 999.9 for a dishwasher tablet pack sold at 359.95.
        (999.9, 359.95, None, True),
        # A 50 % sale from 1999.99 to 999.99 is a real price.
        (999.99, 1999.99, None, False),
        # Only ever 9999 in this store; other stores sell the mower for 26,690.
        (9999, None, 26690, True),
        # The store's own history wins over its peers.
        (999, 1100, 26690, False),
        # No reference at all: a clothing store's 999.99 stays.
        (999.99, None, None, False),
        # Not a 999-family price.
        (1000, 100, None, False),
    ],
)
def test_is_placeholder(price: float, own: float | None, peer: float | None, expected: bool) -> None:
    assert is_placeholder(price, own, peer) is expected


def test_has_three_decimals() -> None:
    assert has_three_decimals(1.769)
    assert not has_three_decimals(1.79)
    assert not has_three_decimals(9.5)


@pytest.mark.parametrize(
    ("price", "own", "peer", "expected"),
    [
        # sehzade: 1.769 TL is 1,769 TL, confirmed by the product's own 1,650 TL days.
        (1.769, 1650.0, None, 1769.0),
        # Confirmed by other stores (Yudum 18 L: 2.139 here, 1,925 elsewhere).
        (2.139, None, 1925.0, 2139.0),
        # Two decimals (1.790 written as 1.79) are repaired when confirmed.
        (1.79, 1815.0, None, 1790.0),
        # Unconfirmed three decimals: missing.
        (1.424, None, None, None),
        # A reference that does not match x1000 does not confirm.
        (1.424, 50.0, None, None),
        # Unconfirmed with at most two decimals: kept.
        (8.5, None, None, 8.5),
        # Prices from 10 up are never touched.
        (37.4, 22.4, None, 37.4),
    ],
)
def test_repair_thousands(price: float, own: float | None, peer: float | None, expected: float | None) -> None:
    assert repair_thousands(price, own, peer) == expected
