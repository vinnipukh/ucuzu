"""Price and product normalization shared by the database build and the API.

Defines the canonical column vocabularies scrapers use (``PRICE_COLUMNS``,
``ID_COLUMNS``, ``NAME_COLUMNS``, ``CATEGORY_COLUMNS``, ``DETAIL_HEADERS``), the
history row shape (``HISTORY_COLUMNS``) and the functions that turn one scraped CSV
frame into normalized history rows plus product details (``DETAIL_COLUMNS``).
Framework-free: no Falcon or database imports.
"""

from __future__ import annotations

import re

import pandas as pd

PRICE_COLUMNS = [
    "member_price",
    "original_price",
    "shown_price",
    "product-price",
    "product_price",
    "price",
    "Price",
    "median_price",
    "Fiyat",
]
ID_COLUMNS = ["Stok Kodu", "sku", "product_id", "UrunID", "id", "Kategori ID"]
NAME_COLUMNS = ["product-name", "product_name", "name", "Product Name", "brand", "District"]
CATEGORY_COLUMNS = ["category", "Category", "Ana Kategori", "Rooms"]
DATE_PATTERN = re.compile(r"(20\d{2})[-_](\d{2})[-_](\d{2})")
HISTORY_COLUMNS = ["date", "retailer", "product_id", "product_name", "category", "price", "source_file"]
# Optional product details some scrapers send, kept beside each history row.
DETAIL_COLUMNS = ["brand", "barcode", "image_url", "product_url", "regular_price"]
# Header spellings per detail, as normalized by ``header_key``, in priority order.
DETAIL_HEADERS = {
    "brand": ("brand", "marka", "markaadi"),
    "barcode": ("barcode", "barkod", "barkodno", "ean", "ean13", "gtin"),
    "image_url": ("imageurl", "image", "resimurl", "resim", "img", "imgurl", "gorsel", "gorselurl", "photourl"),
    "product_url": ("producturl", "url", "link", "urunurl", "urunlinki", "productlink"),
    "regular_price": (
        "regularprice", "normalfiyat", "originalprice", "productoriginalcost", "listprice", "oldprice", "eskifiyat",
    ),
}


def parse_date_from_name(name: str) -> pd.Timestamp | pd.NaT:
    """Return the ``YYYY-MM-DD`` (or ``YYYY_MM_DD``) date embedded in a file name.

    Returns ``NaT`` when there is no such date or it is invalid. The database build
    uses its own, broader ``parse_file_date``; this helper is only used by tests.
    """
    match = DATE_PATTERN.search(name)
    if not match:
        return pd.NaT
    return pd.to_datetime("-".join(match.groups()), errors="coerce")


def coerce_price(value: object) -> float | None:
    """Parse one scraped price string into a float, or ``None`` if it is empty or junk.

    Strips currency markers (``₺``, ``TL``, ``TRY``), quotes and spaces, then
    resolves Turkish/English separators: with both ``,`` and ``.`` the last one is
    the decimal mark; a lone ``,`` followed by 1-2 digits is decimal, otherwise
    thousands; a lone ``.`` followed by exactly 3 digits is a thousands separator.
    Scalar reference for :func:`coerce_price_series`.
    """
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a"}:
        return None

    text = (
        text.replace("₺", "")
        .replace("TL", "")
        .replace("TRY", "")
        .replace('"', "")
        .replace("\xa0", " ")
        .strip()
    )
    text = re.sub(r"[^0-9,.-]", "", text)

    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if re.search(r",\d{1,2}$", text):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        decimal_places = len(text.rsplit(".", 1)[-1])
        if decimal_places == 3 and text.count(".") >= 1:
            text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


def coerce_price_series(series: pd.Series) -> pd.Series:
    """Vectorized price cleaning mirroring :func:`coerce_price` semantics.

    Numeric columns pass through untouched (the common case); object columns
    are cleaned with vectorized string ops instead of per-cell Python calls.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    text = series.astype("string")
    cleaned = (
        text.str.replace("₺", "", regex=False)
        .str.replace("TL", "", regex=False)
        .str.replace("TRY", "", regex=False)
        .str.replace('"', "", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.replace("\u202f", "", regex=False)
        .str.replace(r"[^0-9,.\-]", "", regex=True)
        .str.strip()
    )
    invalid = cleaned.isna() | cleaned.str.fullmatch(r"[-,.]*") | (cleaned == "")
    cleaned = cleaned.mask(invalid, pd.NA)

    has_comma = cleaned.str.contains(",", regex=False)
    has_dot = cleaned.str.contains(".", regex=False)
    comma_last = cleaned.str.rfind(",") > cleaned.str.rfind(".")

    # Both separators present: the LAST one is the decimal separator.
    dec_comma = has_comma & has_dot & comma_last
    dec_dot = has_comma & has_dot & ~comma_last
    # Only comma: trailing 1-2 digits => decimal comma, otherwise thousands.
    only_comma = has_comma & ~has_dot
    comma_is_decimal = only_comma & cleaned.str.contains(r",\d{1,2}$", regex=True)
    comma_is_thousands = only_comma & ~comma_is_decimal
    # Only dot: exactly 3 trailing digits => thousands separator.
    only_dot = has_dot & ~has_comma
    dot_is_thousands = only_dot & cleaned.str.contains(r"\.\d{3}$", regex=True)

    out = cleaned
    if bool(dec_comma.any()):
        out = out.mask(dec_comma, out.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    if bool(dec_dot.any()):
        out = out.mask(dec_dot, out.str.replace(",", "", regex=False))
    if bool(comma_is_decimal.any()):
        out = out.mask(comma_is_decimal, out.str.replace(",", ".", regex=False))
    if bool(comma_is_thousands.any()):
        out = out.mask(comma_is_thousands, out.str.replace(",", "", regex=False))
    if bool(dot_is_thousands.any()):
        out = out.mask(dot_is_thousands, out.str.replace(".", "", regex=False))
    return pd.to_numeric(out, errors="coerce")


def header_key(column: object) -> str:
    """Normalize a CSV header for alias matching (casefold; drop spaces, ``_``, ``-``, dotted-İ mark)."""
    text = str(column).casefold().replace("̇", "")
    return re.sub(r"[\s_\-]", "", text)


def product_details(frame: pd.DataFrame, price_column: str | None = None) -> pd.DataFrame:
    """Extract ``DETAIL_COLUMNS`` from a scraped frame (all ``NA`` where a scraper has none).

    Headers are matched with :func:`header_key` against ``DETAIL_HEADERS``; the
    column already used as the price is never the regular price. Values are cleaned:
    brands are stripped, barcodes must be 8-14 digits, URLs must be absolute
    ``http(s)`` links and regular prices positive numbers.
    """
    by_key: dict[str, object] = {}
    for column in frame.columns:
        if column != price_column:
            by_key.setdefault(header_key(column), column)
    details = pd.DataFrame(index=frame.index)
    for detail, headers in DETAIL_HEADERS.items():
        source = next((by_key[key] for key in headers if key in by_key), None)
        if source is None:
            if detail == "regular_price":
                details[detail] = pd.Series(float("nan"), index=frame.index)
            else:
                details[detail] = pd.Series(pd.NA, index=frame.index, dtype="string")
            continue
        column = frame[source]
        if detail == "regular_price":
            values = coerce_price_series(column)
            details[detail] = values.where(values > 0)
            continue
        if detail == "barcode" and pd.api.types.is_float_dtype(column):
            column = column.map(lambda value: f"{value:.0f}" if pd.notna(value) else pd.NA)
        text = column.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        if detail == "barcode":
            text = text.str.replace(r"\.0$", "", regex=True)
            text = text.where(text.str.fullmatch(r"\d{8,14}").fillna(False))
        elif detail.endswith("_url"):
            text = text.where(text.str.match(r"https?://").fillna(False))
        details[detail] = text.replace("", pd.NA)
    return details


def first_non_empty_column(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Coalesce the first non-blank value per row across ``columns``, in priority order.

    Missing columns are skipped; values are stripped and empty strings count as
    missing. Returns an all-``NA`` string series when none of the columns exist.
    """
    present = [column for column in columns if column in frame.columns]
    if not present:
        return pd.Series(pd.NA, index=frame.index, dtype="string")
    cleaned = {column: frame[column].astype("string").str.strip().replace("", pd.NA) for column in present}
    if len(present) == 1:
        return cleaned[present[0]]
    result = cleaned[present[0]]
    for column in present[1:]:
        result = result.combine_first(cleaned[column])
    return result


def build_product_frame(
    frame: pd.DataFrame,
    retailer: str,
    price_column: str,
    date_value: pd.Timestamp,
    source_file: str,
) -> pd.DataFrame:
    """Normalize one scraped CSV frame into ``HISTORY_COLUMNS`` + ``DETAIL_COLUMNS`` rows.

    ``HousesRent /`` frames with a ``District`` column use district + rooms as the
    product, and ``Cosmetics / Watson`` frames with ``brand`` use sku/brand;
    everything else takes the id, name and category from the canonical column
    lists (name falls back to id and vice versa; category to ``Uncategorized``).
    Prices go through :func:`coerce_price_series`; details come from
    :func:`product_details`. Rows without an id, name or price are dropped.
    """
    # Retailer-specific layouts apply only when their columns are present; newer
    # scrapes of the same retailers use the generic name/price layout.
    if retailer.startswith("HousesRent /") and "District" in frame.columns:
        district = first_non_empty_column(frame, ["District"])
        rooms = first_non_empty_column(frame, ["Rooms"])
        product_name = district.str.cat(rooms.fillna(""), sep=" - ").str.strip(" -")
        product_id = product_name
        category = rooms.fillna("Uncategorized")
    elif retailer == "Cosmetics / Watson" and "brand" in frame.columns:
        brand = first_non_empty_column(frame, ["brand"])
        sku = first_non_empty_column(frame, ["sku"])
        product_id = sku.combine_first(brand)
        product_name = brand.fillna("").str.cat(" (" + sku.fillna("") + ")").str.strip()
        product_name = product_name.str.replace(r"^\s*\((.*)\)$", r"\1", regex=True)
        category = brand.fillna("Uncategorized")
    else:
        product_id = first_non_empty_column(frame, ID_COLUMNS)
        product_name = first_non_empty_column(frame, NAME_COLUMNS).combine_first(product_id)
        product_id = product_id.combine_first(product_name)
        category = first_non_empty_column(frame, CATEGORY_COLUMNS).fillna("Uncategorized")

    prices = coerce_price_series(frame[price_column])
    product_data = pd.DataFrame(
        {
            "date": date_value,
            "retailer": retailer,
            "product_id": product_id,
            "product_name": product_name,
            "category": category,
            "price": prices,
            "source_file": source_file,
        }
    )
    product_data = product_data.join(product_details(frame, price_column))
    product_data = product_data.dropna(subset=["product_id", "product_name", "price"])
    product_data = product_data[
        (product_data["product_id"].astype(str).str.strip() != "")
        & (product_data["product_name"].astype(str).str.strip() != "")
    ]
    return product_data[HISTORY_COLUMNS + DETAIL_COLUMNS]
