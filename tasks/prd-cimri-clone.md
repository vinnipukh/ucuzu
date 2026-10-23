# PRD: ucuzu as a cimri.com clone

Plan for agent-driven work, one Claude Code session per phase. It describes intended changes, not current behaviour. Written 2026-10-23.

## Goal

Turn the ucuzu shop (`frontend/src/routes/(shop)/`, `/api/catalog/*`) into a clone of [cimri.com](https://www.cimri.com): products matched across retailers, unit prices, product families, pack options, photos and store links, price analysis. Build only on the data already committed under `data/`; scraper-side improvements (proposed to the scraper team in two docs) are a bonus, never a dependency.

## Rules for every phase

- Read `AGENTS.md` first and follow it (data rules, architecture boundaries, docs checklists in `docs/DEVELOPMENT.md`, change history in `docs/README.md#change-history`).
- Work directly on `main`; no feature branches. Ask the user before every commit and every push.
- `scripts/build_database.py` must rebuild `data/prices.db` from `data/` alone. Anything the build needs (brand lists, mapping files, overrides) is committed under `data/` (suggested folder: `data/matching/`). No committed file over 85 MB (`uv run python scripts/data_files.py check`).
- Domain logic in `inflation_dashboard/domain/` stays framework-free; database access only in adapters; keep `docs/FALCON_API_CONTRACT.md` and the TypeScript types in sync with API changes.
- Before asking to commit: `uv run pytest`, `uv run python scripts/verify_falcon_api.py`, and for frontend changes `cd frontend && npm run check && npm run build`. A full database build takes about 10 minutes; run it in the background.
- The upstream scraper data is cloned at `../InflationResearchStudy` (import guide: `docs/SETUP.md` §4). Header aliases for category and product id were fixed on 2026-10-23 (`c1c76e9`).

## Decisions already made (do not re-ask)

- **Extraction:** rule-based first (phase 1), then a trained tagger + clustering (phase 5). Everything going into and out of the tagger/clustering is checked by an LLM, using Haiku subagents (high effort). LLM verdicts are stored in a committed mapping file so the build stays deterministic.
- **Same product = what cimri does:** different size, colour/shade, model code or variant (fat %, flavour, lactose-free, organic, packaging such as glass vs carton, UHT vs pasteurised) = different products. Warranty/seller wording ("İthalatçı Garantili"), marketing words, letter case and word order are ignored. When unsure, do not merge.
- **Sizes and families:** every size is its own product (shown alone in search). Products also form a **family** = the product without its size (e.g. "Brand A osmancık bulgur" 100 g / 500 g / 1 kg); families are reachable from the product page and from category pages, like cimri's family pages (`…-fiyatlari,a2393572193`).
- **Multipacks of the same size** (6 × 1 L) are **pack options** on the single product's page with a price per package, like cimri's "Paket Seçenekleri".
- **IDs:** our own permanent numeric product and family IDs, cimri-style slug URLs (`/urun/<slug>,<id>`). No users yet, so old `name_key` URLs need no redirects.
- **Units:** TL/adet like cimri (per piece for counted goods such as diapers and eggs; per package for multipacks). Beyond cimri: store TL/ml and TL/g, show them as TL/L and TL/kg; TL/wash for detergents ("24 yıkama"); TL/m for cable and hose; TL/m² for tiles and laminate; no unit price for capacities (fridge litres, scale kg) and none when the title has no size.
- **Brands:** from the retailers' own data (A101 `marka`, Macrocenter `Brand`, GoldenRose `Brand`, the Watsons brand list) plus brands learned from titles (first word sold by 3+ stores), reviewed and committed.
- **Overrides** (manual merge/split corrections) are approved by the Haiku checks for now.
- **Precision target:** 95%+ on hand-labelled pairs.
- **Analysis dashboard (`/analiz`):** move into the shop only what cimri has (per-product price analysis) plus a few extras; the standalone dashboard is deleted at the end (phase 8).
- **Shrinkflation:** a separate view, not a change to the inflation methodology.
- The June–September 2026 data gap is expected.

## Reference material

- Prototype parser and audit (scratch, not in the repo): `C:\Users\arhan\AppData\Local\Temp\claude\C--hyperboria-ucuzu\d71d063e-a8d9-426e-a2eb-b55575d92eea\scratchpad\parse_lib.py` and `unit_audit.py`. Results on current Markets data: size found in 82.9% of titles; products sold in 2+ stores 4,397 → 6,963 (+58%) with a simple key. Lessons: keep bare numbers (shade/model codes) in the key; Turkish thousands separators in sizes (`1.440 Ml`, `1,850 ml`); diaper weight ranges (`7-14 Kg`), lumens (`720 L`), dimensions (`50x70`) and capacities (`180 Kg kapasiteli`, `451 Lt buzdolabı`) are not contents; the letter `L` in `L Gönye` is a shape.
- Scraper-team docs (context only): "Scraped Data Quality Report" https://claude.ai/artifact/Npcrocq8dPspB5NHUjrQ7s and "Scraping Requirements for a Cimri-Level Shop" https://claude.ai/artifact/AryntYpVt4PpEW6tu7K8W8.
- Known data problems (phase 2): placeholder prices 999 / 999.99 / 9999 (Karaca, EnglishHome, Mudo, Beymen, Rossmann, Ikea, Gratis, …); 228 zero/negative prices; sehzade stores 1,769 TL as 1.769; duplicate retailers `Cosmetics / Watson` + `Cosmetics / Watsons`, `ConstructionSuppliesMarkets / Koctas` + `Koçtaş`, `Communication / VatanComputer` + `Vatan Computer`; BizimMarket prices are whole cases while titles describe one item.

## Phases (in order)

Phases run strictly one at a time, in the order below (the user's choice); the next phase starts only after the previous one is committed. Each phase ends with tests green, docs updated, a change-history entry, and a commit the user approved.

### Phase 1 — Extra columns, title parser, brand list, unit prices

1. **Keep the extra columns scrapers already send:** `brand`, `barcode`, `image_url`, `product_url`, `regular_price` (A101 `marka`/`barkod`/`resim_url`/`url`/`normal_fiyat`; Macrocenter `Brand`/`RegularPrice`; GoldenRose `Brand`/`Image URL`/`Product URL`; Cagri and Hapeloglu `product_url`/`image_url`; Arden `link`/`resim`; DR, Nezih, Loft). Carry them through `build_product_frame` → `csv_to_json.py` (JSON fields, newest non-empty value wins) → database (`products` columns). Re-import affected retailers from `../InflationResearchStudy`.
2. **Title parser** `inflation_dashboard/domain/product_attributes.py`: `parse(name) -> ParsedName(brand, base_tokens, amount, unit, pack, attrs, model_codes, kind)` where `kind` separates contents from capacity/dimensions. Pure functions, table-driven tests with real titles, including must-not-merge cases (Pastel Oje 112 vs 380, Piranha 7849 vs 7889, yarım vs tam yağlı, 200 ml vs 1 L).
3. **Brand list** `data/matching/brands.json` built by a script from the retailer brand columns + titles; multi-word brands (`air wick`, `la lorraine`).
4. **Unit prices** per the unit decisions; computed in the build, stored on `products` (`unit_price`, `unit_price_unit`).
5. Done when: size found for ~90% of Markets titles, unit prices present, all tests and API checks pass. API exposure of the new fields can wait for phase 3 unless trivial.

### Phase 2 — Data clean-up during the build

Mark placeholder (999 / 999.99 / 9999 family) and ≤ 0 prices as missing; merge the duplicate retailer folders into one label each; flag BizimMarket case prices so they never rank as cheapest; repair sehzade three-decimal prices only where clearly safe (price < 10 with three decimals and a peer price ~1000× higher). Report counts in the build summary. Done when no fake price can be "cheapest" in `/api/catalog/*`.

### Phase 3 — Matching v1, IDs, families, pack options

`match_key` and `family_key` from the parsed attributes (cimri's same-product rules); permanent numeric product/family IDs assigned by a script into a committed `data/matching/ids.json`; `data/matching/overrides.json` (merge/split, applied last); multipacks attach to their single-size product as pack options. New/changed tables, `/api/catalog/*` responses keyed by our IDs, contract + TypeScript types + docs. Done when the shop groups by the new keys and multi-store products grow roughly as in the prototype (+58% on Markets).

### Phase 4 — Measurement and Haiku checks

Labelled set of ~500 product pairs under `data/matching/eval/`; a script reporting precision/recall; Haiku subagents (high effort) review doubtful groups and write approved overrides. Done when precision ≥ 95% is measured and reported.

### Phase 5 — Trained tagger + clustering (after phase 4)

A trained title tagger and char n-gram TF-IDF clustering (blocking by category group + brand + size) for titles the rules miss; Haiku checks inputs and outputs; results land in the mapping file. Done when matches grow with precision still ≥ 95%.

### Phase 6 — Shop UI, the cimri parts (after phase 3)

ID-based URLs; unit price on product cards and offer rows; family pages and selectors; pack options; photos and "Mağazaya Git" buttons where we have them; a "Fiyat Analizi" block (lowest/highest/average for 1/3/6/12 months, "Son 30 günün en ucuzu"). Reuse the price-history code behind the old dashboard where it helps.

### Phase 7 — Extras on top of cimri (after phase 6)

Category price-change line ("Süt fiyatları son 12 ayda %X arttı"); biggest rises and drops on the deals page; shrinkflation view (same store product, size down ≥ 5% with package price within ±3% or up; confirmed across stores; Haiku check on doubtful pairs).

### Phase 8 — Remove the old dashboard (after phases 6–7)

Delete `/analiz`, its views and components, the endpoints only it uses (`/api/inventory`, `/history`, `/retailer-averages`, `/movers`, `/coverage`, `/products`, `/products/search`, `/product`, `/epeykatfg/monthly-inflation` — check each first) and the adapter/application code behind them; decide with the user what happens to `data/inflation/` (1.9 GB, the app reads one file). Update `AGENTS.md`, docs and contract.
