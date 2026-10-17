"""Falcon resources: one class per ``/api/*`` route.

The data resources share one pattern: serve the pre-serialized response cache
when the same endpoint and query string were answered within the TTL; otherwise
parse the common filters, load the filtered history, run the application use
case, wrap the result with ``serialization.envelope`` and cache and send it
(``_send_response``). Filter validation errors become 400 ``invalid_filter``
envelopes here; every other error is rendered by the handlers registered in
``falcon_app.create_app``. Response shapes are specified in
docs/FALCON_API_CONTRACT.md.
"""

from __future__ import annotations

from typing import Any

import falcon
import orjson

from inflation_dashboard.adapters import sqlite_price_repository
from inflation_dashboard.api.filters import (
    RESPONSE_CACHE_TTL_SECONDS,
    ApiFilterError,
    get_cached_response,
    get_inventory,
    is_sqlite_available,
    load_filtered_history,
    make_etag,
    parse_common_filters,
    parse_date_param,
    put_cached_response,
    require_database,
)
from inflation_dashboard.api.serialization import envelope, error_envelope, json_safe_mapping, records_from_frame
from inflation_dashboard.application.chart_specs import (
    BIGGEST_DROPS_COLUMNS,
    BIGGEST_GAINS_COLUMNS,
    CATEGORY_COVERAGE_COLUMNS,
    COVERAGE_OVER_TIME_COLUMNS,
    PRODUCT_HISTORY_COLUMNS,
    RETAILER_AVERAGE_COLUMNS,
    SKIPPED_DIAGNOSTICS_COLUMNS,
)
from inflation_dashboard.application.epeykatfg_monthly import load_monthly_inflation
from inflation_dashboard.application.use_cases import (
    calculate_category_coverage,
    calculate_coverage_over_time,
    calculate_coverage_summary,
    calculate_price_movers,
    calculate_retailer_average_trends,
    get_product_history,
    list_inventory_filters,
    summarize_product_history,
)
from inflation_dashboard.domain.prices import HISTORY_COLUMNS


def _accepts_gzip(req: Any) -> bool:
    """Return True when the client's Accept-Encoding permits a gzip response."""

    header = req.get_header("Accept-Encoding")
    if not header:
        return False
    best_quality = 0.0
    for part in header.split(","):
        token = part.strip()
        quality = 1.0
        if ";" in token:
            token, _, parameters = token.partition(";")
            token = token.strip()
            for parameter in parameters.split(";"):
                parameter = parameter.strip()
                if parameter.lower().startswith("q="):
                    try:
                        quality = float(parameter[2:])
                    except ValueError:
                        quality = 0.0
        if token.lower() == "gzip":
            best_quality = max(best_quality, quality)
    return best_quality > 0.0


def _etag_matches(req: Any, etag_value: str) -> bool:
    """RFC 7232 If-None-Match match (weak or strong; `*` is a wildcard match)."""

    etags = req.if_none_match
    if not etags:
        return False
    for etag in etags:
        if etag == "*" or etag == etag_value:
            return True
    return False


def _emit_cached_response(resp: Any, req: Any, body: bytes, etag_value: str, encoding: str | None, *, vary: bool) -> None:
    """Serve pre-serialized bytes with ETag/Cache-Control and optional gzip.

    Responds 304 Not Modified when the client already holds this representation
    (Falcon strips the body and Content-Type automatically for 304); otherwise
    200 with the payload body.
    """

    cache_control = ["public", f"max-age={RESPONSE_CACHE_TTL_SECONDS}"]
    if _etag_matches(req, etag_value):
        resp.status = falcon.HTTP_304
        resp.etag = etag_value
        resp.cache_control = cache_control
        if vary:
            resp.vary = ["Accept-Encoding"]
        return
    resp.status = falcon.HTTP_200
    resp.etag = etag_value
    resp.cache_control = cache_control
    resp.data = body
    resp.content_type = falcon.MEDIA_JSON
    if encoding:
        resp.set_header("Content-Encoding", encoding)
    if vary:
        resp.vary = ["Accept-Encoding"]


def _serve_cached(resp: Any, req: Any, endpoint: str, query_string: str) -> bool:
    """Serve the cached payload variant for this request; return True when served.

    Selects gzip vs raw from Accept-Encoding. Each variant carries its own
    strong ETag (a gzip representation is a different representation), and
    `Vary: Accept-Encoding` keeps shared caches honest.
    """

    cached = get_cached_response(endpoint, query_string)
    if cached is None:
        return False
    req.context["_cache_hit"] = True
    raw_bytes, gzip_bytes, etag, gzip_etag = cached
    if gzip_bytes is not None and _accepts_gzip(req):
        body, body_etag, encoding = gzip_bytes, gzip_etag, "gzip"
    else:
        body, body_etag, encoding = raw_bytes, etag, None
    _emit_cached_response(resp, req, body, body_etag, encoding, vary=gzip_bytes is not None)
    return True


def _send_response(resp: Any, req: Any, endpoint: str, query_string: str, envelope_dict: dict[str, object]) -> None:
    """Cache the pre-serialized response and serve it immediately (200 or 304)."""
    try:
        raw_bytes = orjson.dumps(envelope_dict)
        put_cached_response(endpoint, query_string, raw_bytes)
        if not _serve_cached(resp, req, endpoint, query_string):
            # Entry was evicted between put and get (rare under cache pressure);
            # serve the freshly serialized bytes without variant headers.
            _emit_cached_response(resp, req, raw_bytes, make_etag(raw_bytes), None, vary=False)
        # This response was computed just now, not served from a warm cache.
        req.context["_cache_hit"] = False
    except Exception:
        resp.status = falcon.HTTP_200
        resp.media = envelope_dict


class HealthResource:
    """``GET /api/health``: cheap liveness probe that never reads data."""

    def on_get(self, req: Any, resp: Any) -> None:
        """Return 200 ``{status: "ok", database: "available" | "unavailable"}``.

        ``database`` reports whether the configured database file exists and is
        non-empty. Not cached.
        """
        resp.status = falcon.HTTP_200
        database = "available" if is_sqlite_available() else "unavailable"
        resp.media = envelope({"status": "ok", "database": database}, meta={"service": "inflation-dashboard-api"})


class InventoryResource:
    """``GET /api/inventory``: retailer list and overall date range."""

    def on_get(self, req: Any, resp: Any) -> None:
        """No parameters.

        ``data``: sorted ``retailers`` and ISO-datetime ``min_date``/``max_date``;
        ``meta``: ``file_count`` and its duplicate ``inventory_file_count``.
        503 ``database_unavailable`` without a database.
        """
        if _serve_cached(resp, req, "inventory", req.query_string):
            return

        inventory = get_inventory()
        filters = list_inventory_filters(inventory)
        envelope_dict = envelope(
            {
                "retailers": filters["retailers"],
                "min_date": filters["min_date"],
                "max_date": filters["max_date"],
            },
            meta={"file_count": filters["file_count"], "inventory_file_count": filters["file_count"]},
        )
        _send_response(resp, req, "inventory", req.query_string, envelope_dict)


class HistoryResource:
    """``GET /api/history``: filtered observations, or one product's series."""

    def on_get(self, req: Any, resp: Any) -> None:
        """Common filters plus optional ``product_name`` and ``product_retailer``.

        Without ``product_name``, ``data.history`` holds every filtered row, and a
        "history response may be large" warning is added for all-history requests
        or more than 5000 rows. With it, ``data.history`` is that product's series
        and ``data.summary`` its latest/cheapest/change metrics; ``product_retailer``
        defaults to the only selected retailer (400 when several are selected).
        """
        try:
            if _serve_cached(resp, req, "history", req.query_string):
                return

            parsed_filters = parse_common_filters(req)
            history, skipped, meta = load_filtered_history(parsed_filters)
            product_name = req.get_param("product_name", default=None)
            product_retailer = req.get_param("product_retailer", default=None)
            if product_name:
                retailer = product_retailer or _single_selected_retailer(parsed_filters.selected_retailers)
                product_history = get_product_history(history, retailer, product_name)
                data = {
                    "history": records_from_frame(product_history, PRODUCT_HISTORY_COLUMNS),
                    "summary": json_safe_mapping(summarize_product_history(product_history)),
                }
                meta = {**meta, "product_name": product_name, "product_retailer": retailer}
            else:
                data = {"history": records_from_frame(history, HISTORY_COLUMNS)}
                if parsed_filters.all_history or len(history) > 5000:
                    meta = {**meta, "warnings": [*meta.get("warnings", []), "history response may be large"]}
            envelope_dict = envelope(data, meta=meta)
            _send_response(resp, req, "history", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


class RetailerAveragesResource:
    """``GET /api/retailer-averages``: average or median price per retailer per date."""

    def on_get(self, req: Any, resp: Any) -> None:
        """Common filters plus ``aggregation`` (``Average`` or ``Median``, else 400).

        ``data.records`` and its duplicate ``data.retailer_averages`` hold
        ``{date, retailer, price}`` rows; ``meta`` adds ``aggregation``.
        """
        try:
            if _serve_cached(resp, req, "retailer-averages", req.query_string):
                return

            aggregation = req.get_param("aggregation", default="Average")
            if aggregation not in {"Average", "Median"}:
                raise ApiFilterError(
                    "invalid_filter",
                    "Invalid aggregation",
                    meta={"filters": {"aggregation": aggregation}},
                )
            parsed_filters = parse_common_filters(req)
            history, skipped, meta = load_filtered_history(parsed_filters)
            trends = calculate_retailer_average_trends(history, parsed_filters.selected_retailers, aggregation)
            records = records_from_frame(trends, RETAILER_AVERAGE_COLUMNS)
            envelope_dict = envelope(
                {"records": records, "retailer_averages": records},
                meta={**meta, "aggregation": aggregation, "skipped_file_count": len(skipped)},
            )
            _send_response(resp, req, "retailer-averages", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


class MoversResource:
    """``GET /api/movers``: biggest drops from peak and gains since first observation."""

    def on_get(self, req: Any, resp: Any) -> None:
        """Common filters plus ``scope_retailer`` and ``limit``.

        ``scope_retailer`` is ``All retailers`` (default) or one selected retailer.
        ``limit`` must be 5-30 (default 10); ``mover_count`` is an alias that
        supplies the default and is validated too. ``data``: ``biggest_drops`` and
        ``biggest_gains``; ``meta`` adds ``scope_retailer``, ``limit`` and
        ``eligible_product_count``.
        """
        try:
            if _serve_cached(resp, req, "movers", req.query_string):
                return

            parsed_filters = parse_common_filters(req)
            history, skipped, meta = load_filtered_history(parsed_filters)
            scope_retailer = req.get_param("scope_retailer", default="All retailers")
            if scope_retailer != "All retailers" and scope_retailer not in parsed_filters.selected_retailers:
                raise ApiFilterError(
                    "invalid_filter",
                    f"Unknown retailer: {scope_retailer}",
                    meta={"filters": {"scope_retailer": scope_retailer}},
                )
            limit = _parse_bounded_int(
                req,
                "limit",
                default=_parse_bounded_int(req, "mover_count", default=10, minimum=5, maximum=30),
                minimum=5,
                maximum=30,
            )
            mover_results = calculate_price_movers(history, scope_retailer, limit)
            stats = mover_results["stats"]
            envelope_dict = envelope(
                {
                    "biggest_drops": records_from_frame(mover_results["biggest_drops"], BIGGEST_DROPS_COLUMNS),
                    "biggest_gains": records_from_frame(mover_results["biggest_gains"], BIGGEST_GAINS_COLUMNS),
                },
                meta={
                    **meta,
                    "scope_retailer": scope_retailer,
                    "limit": limit,
                    "eligible_product_count": int(len(stats)),
                    "skipped_file_count": len(skipped),
                },
            )
            _send_response(resp, req, "movers", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


class CoverageResource:
    """``GET /api/coverage``: observation counts over time and per category."""

    def on_get(self, req: Any, resp: Any) -> None:
        """Common filters plus ``category_limit`` (>= 1, default 20).

        ``data``: ``summary``, ``coverage_over_time``, ``category_coverage`` (top
        ``category_limit`` retailer/category pairs) and ``skipped_files``, which is
        always empty with the SQLite adapter.
        """
        try:
            if _serve_cached(resp, req, "coverage", req.query_string):
                return

            parsed_filters = parse_common_filters(req)
            history, skipped, meta = load_filtered_history(parsed_filters)
            category_limit = _parse_bounded_int(req, "category_limit", default=20, minimum=1)
            summary = calculate_coverage_summary(history, skipped)
            coverage_over_time = calculate_coverage_over_time(history)
            category_coverage = calculate_category_coverage(history, limit=category_limit)
            envelope_dict = envelope(
                {
                    "summary": summary,
                    "coverage_over_time": records_from_frame(coverage_over_time, COVERAGE_OVER_TIME_COLUMNS),
                    "category_coverage": records_from_frame(category_coverage, CATEGORY_COVERAGE_COLUMNS),
                    "skipped_files": records_from_frame(skipped, SKIPPED_DIAGNOSTICS_COLUMNS),
                },
                meta={**meta, "category_limit": category_limit, "skipped_file_count": len(skipped)},
            )
            _send_response(resp, req, "coverage", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


class ProductListResource:
    """``GET /api/products``: distinct product names per retailer, for product pickers."""

    def on_get(self, req: Any, resp: Any) -> None:
        """``retailer`` (repeatable, required) and optional ``start_date``/``end_date``.

        Every retailer must be in the inventory. Only products observed inside the
        date window are listed. ``data`` is ``[{retailer, products: [name, ...]}]``
        sorted by retailer and name; ``meta`` has ``retailers``, ``start_date``,
        ``end_date`` and ``product_count``. Much smaller than ``/api/history``.
        """
        try:
            if _serve_cached(resp, req, "products", req.query_string):
                return

            retailers = [retailer for retailer in (req.get_param_as_list("retailer") or []) if retailer]
            if not retailers:
                raise ApiFilterError("invalid_filter", "retailer is required", meta={"filters": {"retailer": []}})
            available = set(list_inventory_filters(get_inventory()).get("retailers") or [])
            unknown = sorted(set(retailers) - available)
            if unknown:
                raise ApiFilterError(
                    "invalid_filter",
                    f"Unknown retailer: {unknown[0]}",
                    meta={"filters": {"retailer": retailers}},
                )
            start_date = parse_date_param(req, "start_date", None)
            end_date = parse_date_param(req, "end_date", None)
            if start_date and end_date and start_date > end_date:
                raise ApiFilterError(
                    "invalid_filter",
                    "Invalid date range",
                    meta={"filters": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}},
                )

            groups = sqlite_price_repository.list_product_names(retailers, start_date, end_date)
            envelope_dict = envelope(
                groups,
                meta={
                    "retailers": retailers,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "product_count": sum(len(group["products"]) for group in groups),
                },
            )
            _send_response(resp, req, "products", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


class ProductSearchResource:
    """``GET /api/products/search``: product autocomplete over the product_prices view."""

    def on_get(self, req: Any, resp: Any) -> None:
        """``q`` (or ``query``), optional ``retailer`` and ``category``, ``limit`` 1-100.

        ``q`` is a SQL ``LIKE '%q%'`` match on product name or id; ``retailer`` and
        ``category`` are exact filters; a ``limit`` outside 1-100 is a 400 (not
        clamped). ``data`` is a list of product summaries ordered by observation
        count. A failing repository query yields ``[]``; a missing database is a 503.
        """
        try:
            if _serve_cached(resp, req, "products-search", req.query_string):
                return

            query = (req.get_param("q") or req.get_param("query") or "").strip()
            retailer = req.get_param("retailer", default=None)
            category = req.get_param("category", default=None)
            limit = _parse_bounded_int(req, "limit", default=20, minimum=1, maximum=100)
            require_database()

            results: list[dict[str, object]] = []
            try:
                results = sqlite_price_repository.search_products(
                    query=query,
                    retailer=retailer,
                    category=category,
                    limit=limit,
                )
            except Exception:
                results = []

            meta = {
                "query": query,
                "retailer": retailer,
                "category": category,
                "limit": limit,
                "count": len(results),
            }
            envelope_dict = envelope(results, meta=meta)
            _send_response(resp, req, "products-search", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


class ProductDetailResource:
    """``GET /api/product``: one product's summary and complete price history."""

    def on_get(self, req: Any, resp: Any) -> None:
        """``product_id`` or ``product_name`` (one required), optional ``retailer``.

        ``product_name`` is ignored when ``product_id`` is given. ``data`` is the
        product summary plus ``price_history`` (date -> price), ``history`` and
        ``summary``; ``meta`` has ``product_id``, ``retailer`` and
        ``observations_count``. No match, or an error during the lookup, returns a
        404 ``not_found`` envelope echoing the request in ``meta``.
        """
        try:
            if _serve_cached(resp, req, "product-detail", req.query_string):
                return

            product_id = req.get_param("product_id", default=None)
            retailer = req.get_param("retailer", default=None)
            product_name = req.get_param("product_name", default=None)

            lookup_key = product_id or product_name
            if not lookup_key:
                raise ApiFilterError(
                    "invalid_filter",
                    "product_id or product_name is required",
                    meta={"filters": {"product_id": product_id, "product_name": product_name}},
                )

            require_database()
            detail: dict[str, object] | None = None
            try:
                detail = sqlite_price_repository.get_product_price_history(
                    product_id=lookup_key,
                    retailer=retailer,
                )
            except Exception:
                detail = None

            if not detail:
                resp.status = falcon.HTTP_404
                resp.media = error_envelope(
                    "not_found",
                    f"Product not found: {lookup_key}",
                    meta={"product_id": product_id, "product_name": product_name, "retailer": retailer},
                )
                return

            meta = {
                "product_id": detail.get("product_id"),
                "retailer": detail.get("retailer"),
                "observations_count": detail.get("observations_count", 0),
            }
            envelope_dict = envelope(detail, meta=meta)
            _send_response(resp, req, "product-detail", req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)


def _set_filter_error(resp: Any, exc: ApiFilterError) -> None:
    """Render an ApiFilterError as a 400 envelope with its code, message and meta."""
    resp.status = falcon.HTTP_400
    resp.media = error_envelope(exc.code, exc.message, meta=exc.meta)


def _single_selected_retailer(selected_retailers: list[str]) -> str:
    """Return the only selected retailer, or raise 400 ``product_retailer is required``."""
    if len(selected_retailers) == 1:
        return selected_retailers[0]
    raise ApiFilterError(
        "invalid_filter",
        "product_retailer is required",
        meta={"filters": {"selected_retailers": selected_retailers}},
    )


def _parse_bounded_int(req: Any, name: str, *, default: int, minimum: int, maximum: int | None = None) -> int:
    """Parse integer query parameter ``name``; absent or empty returns ``default``.

    Raises ApiFilterError (``invalid_filter``, ``Invalid <name>``) when the value
    is not an integer or lies outside ``[minimum, maximum]``; it is never clamped.
    """
    raw_value = req.get_param(name, default=None)
    if raw_value in {None, ""}:
        return default
    try:
        parsed_value = int(str(raw_value))
    except ValueError as exc:
        raise ApiFilterError("invalid_filter", f"Invalid {name}", meta={"filters": {name: raw_value}}) from exc
    if parsed_value < minimum or (maximum is not None and parsed_value > maximum):
        raise ApiFilterError("invalid_filter", f"Invalid {name}", meta={"filters": {name: raw_value}})
    return parsed_value


class EpeyKatfgMonthlyResource:
    """``GET /api/epeykatfg/monthly-inflation``: the EpeyKatfg monthly inflation CSV."""

    def on_get(self, req: Any, resp: Any) -> None:
        """No parameters; does not need the database.

        ``data``: one dict per CSV row (numbers parsed where possible); ``meta``:
        ``count``, ``columns``, ``source`` and ``notes``. A missing file gives
        ``data: []``.
        """
        ENDPOINT = "epeykatfg-monthly"
        try:
            if _serve_cached(resp, req, ENDPOINT, req.query_string):
                return
            rows, header = load_monthly_inflation()
            envelope_dict = envelope(
                rows,
                meta={
                    "count": len(rows),
                    "columns": header,
                    "source": "EpeyKatfg monthly inflation artifact (EPEYKATFG_MONTHLY_CSV)",
                    "notes": "TUIK 2026 weights normalised to 100% over covered groups "
                             "03,05,06,08,09,13 (30.551% of basket); TUIK 07 excluded from "
                             "weighting (small sample, --min-group-n 20).",
                },
            )
            _send_response(resp, req, ENDPOINT, req.query_string, envelope_dict)
        except ApiFilterError as exc:
            _set_filter_error(resp, exc)
