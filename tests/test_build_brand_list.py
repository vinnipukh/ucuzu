from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_brand_list  # noqa: E402


def _partition(data: Path, stem: str, products: dict[str, dict]) -> None:
    path = data / "prices_json" / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")


def _product(name: str, brand: str | None = None, day: str = "2026-10-20") -> dict:
    product = {"name": name, "category": "Gıda", "prices": {day: 10.0}}
    if brand:
        product["brand"] = brand
    return product


def test_brand_list_sources(tmp_path: Path) -> None:
    data = tmp_path / "data"
    stores = ["Markets_A", "Markets_B", "Markets_C"]
    for index, stem in enumerate(stores):
        _partition(
            data,
            stem,
            {
                **{f"1{i}": _product(f"Air Wick Oda Kokusu {i} 250 ml") for i in range(4)},
                "2": _product("Ülker Bisküvi 100 g"),
                "3": _product("Domates Salçası 830 g" if index else "Tat Domates Salçası 830 g"),
                "4": _product("Domates Kg"),
                "5": _product("Yayla Pirinç 1 kg", brand="Yayla" if index == 0 else None),
                # A supplier name that never starts a title is not a brand.
                **({"6": _product("Defter A4", brand="Gıpta Dağıtım")} if index == 0 else {}),
                # Old titles do not teach brands.
                "7": _product(f"Eskimarka Çay {index}", day="2026-01-01"),
            },
        )
    # "domates" starts titles in three stores but is mid-title as often: not a brand.
    for stem in stores:
        _partition(data, stem + "x", {"1": _product("Tat Domates Salçası 830 g"), "2": _product("Tat Domates Püresi")})
    _partition(data, "Cosmetics_Watson", {"1": {"name": "DOVE (1)", "category": "DOVE", "prices": {"2026-04-22": 5}}})
    _partition(data, "HousesRent_Ankara", {str(i): _product(f"Çankaya {i}") for i in range(5)})
    (data / "matching").mkdir()
    (data / "matching" / "brand_overrides.json").write_text(
        json.dumps({"add": ["La Lorraine"], "remove": ["ulker"]}), encoding="utf-8"
    )

    payload = build_brand_list.build(data)

    brands = {brand["key"]: brand for brand in payload["brands"]}
    assert set(brands) == {"air wick", "yayla", "dove", "la lorraine", "tat"}
    assert brands["air wick"] == {"name": "Air Wick", "key": "air wick", "sources": ["titles"], "stores": 3}
    assert brands["yayla"]["sources"] == ["retailer", "titles"]
    assert brands["dove"] == {"name": "Dove", "key": "dove", "sources": ["watsons"], "stores": 0}
    assert brands["la lorraine"]["sources"] == ["override"]

    output = data / "matching" / "brands.json"
    build_brand_list.write(payload, output)
    assert json.loads(output.read_text(encoding="utf-8")) == payload
