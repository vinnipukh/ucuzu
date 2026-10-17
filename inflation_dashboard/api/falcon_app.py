"""Falcon WSGI application factory.

``create_app()`` registers the ten ``/api/*`` routes, the timing and CORS
middleware, the orjson media handlers and the error handlers that render every
error (404/405, unhandled 500, 503 database unavailable) in the
``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

import logging
import os
import time

import falcon

import orjson

from inflation_dashboard.api import resources
from inflation_dashboard.api.filters import DatabaseUnavailableError
from inflation_dashboard.api.serialization import error_envelope

_LOGGER = logging.getLogger("inflation_dashboard.api.timing")
_ERROR_LOGGER = logging.getLogger("inflation_dashboard.api")

SERVER_ERROR_MESSAGE = "Internal server error"
_HTTP_ERROR_CODES = {404: "not_found", 405: "method_not_allowed"}


class TimingMiddleware:
    """Per-request duration + cache-hit logging, opt-in via FALCON_TIMING_LOG=1.

    Does no measurable work when disabled (one attribute read per request).
    When enabled, records a perf_counter in ``process_request`` and emits one
    INFO line per request with method, path, status, duration and whether the
    response came from the pre-serialized byte cache.
    """

    enabled: bool

    def __init__(self) -> None:
        self.enabled = os.getenv("FALCON_TIMING_LOG", "").strip().lower() in {"1", "true", "yes", "on"}

    def process_request(self, req: object, resp: object) -> None:
        """Record the request start time when timing logs are enabled."""
        if self.enabled:
            req.context["_started_at"] = time.perf_counter()

    def process_response(self, req: object, resp: object, resource: object, req_succeeded: bool | None = None) -> None:
        """Log one INFO line (method, path, status, duration, cache hit) when enabled."""
        if not self.enabled:
            return
        started_at = req.context.get("_started_at")
        if started_at is None:
            return
        duration_ms = (time.perf_counter() - started_at) * 1000.0
        _LOGGER.info(
            "falcon_request method=%s path=%s status=%s duration_ms=%.2f cache_hit=%s",
            req.method,
            req.path,
            resp.status,
            duration_ms,
            req.context.get("_cache_hit", False),
        )

# orjson serializes large record payloads several times faster than stdlib
# json.dumps; every value leaving the API is already JSON-native (NaN/NaT are
# mapped to None by serialization.to_json_value), so orjson's strict mode is
# safe.
_JSON_HANDLER = falcon.media.JSONHandler(dumps=orjson.dumps, loads=orjson.loads)

# Cross-origin access for the Svelte frontend (documented in
# docs/FALCON_API_CONTRACT.md and docs/ARCHITECTURE.md). The launcher
# (scripts/run_falcon_server.py) exposes this as --cors-origins /
# FALCON_CORS_ORIGINS; default is open access ("*").
def _cors_middleware():
    """Build Falcon's CORSMiddleware from ``FALCON_CORS_ORIGINS``.

    The variable is a comma-separated origin list; ``*`` (the default) allows any
    origin. Preflight ``OPTIONS`` requests are answered by the middleware; no
    response headers are exposed.
    """
    raw_origins = os.getenv("FALCON_CORS_ORIGINS", "*")
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    # Falcon requires the "*" wildcard as a plain string, not inside a list.
    allow_origins: str | list[str] = "*" if origins == ["*"] else origins
    # Falcon's CORSMiddleware handles GET/OPTIONS preflights automatically.
    return falcon.CORSMiddleware(allow_origins=allow_origins, expose_headers=[])


def _handle_database_unavailable(req: object, resp: object, ex: DatabaseUnavailableError, params: object) -> None:
    """Render DatabaseUnavailableError as a 503 ``database_unavailable`` envelope."""
    resp.status = falcon.HTTP_503
    resp.media = error_envelope(ex.code, ex.message)


def _handle_http_error(req: object, resp: object, ex: falcon.HTTPError, params: object) -> None:
    """Render a Falcon HTTPError (unknown route, wrong method, ...) as an envelope.

    404 -> ``not_found``, 405 -> ``method_not_allowed``, any other status ->
    ``http_error``. Headers Falcon set on the error (such as ``Allow``) are kept.
    """
    code = _HTTP_ERROR_CODES.get(ex.status_code, "http_error")
    resp.status = ex.status
    for name, value in (ex.headers or {}).items():
        resp.set_header(name, value)
    resp.media = error_envelope(code, ex.description or ex.title)


def _handle_unexpected_error(req: object, resp: object, ex: Exception, params: object) -> None:
    """Log an unhandled exception and return a 500 ``server_error`` envelope.

    The traceback goes to the ``inflation_dashboard.api`` logger; the response
    message is always ``SERVER_ERROR_MESSAGE``, so exception text never reaches
    the client.
    """
    _ERROR_LOGGER.exception("Unhandled error on %s %s", req.method, req.path)
    resp.status = falcon.HTTP_500
    resp.media = error_envelope("server_error", SERVER_ERROR_MESSAGE)


def create_app() -> falcon.App:
    """Create the Falcon WSGI application and register API resources."""

    app = falcon.App(middleware=[TimingMiddleware(), _cors_middleware()])
    app.req_options.media_handlers[falcon.MEDIA_JSON] = _JSON_HANDLER
    app.resp_options.media_handlers[falcon.MEDIA_JSON] = _JSON_HANDLER
    # Falcon picks the most specific handler, so HTTPError (404/405 from routing)
    # and DatabaseUnavailableError are not shadowed by the catch-all Exception.
    app.add_error_handler(Exception, _handle_unexpected_error)
    app.add_error_handler(falcon.HTTPError, _handle_http_error)
    app.add_error_handler(DatabaseUnavailableError, _handle_database_unavailable)
    app.add_route("/api/health", resources.HealthResource())
    app.add_route("/api/inventory", resources.InventoryResource())
    app.add_route("/api/history", resources.HistoryResource())
    app.add_route("/api/retailer-averages", resources.RetailerAveragesResource())
    app.add_route("/api/movers", resources.MoversResource())
    app.add_route("/api/coverage", resources.CoverageResource())
    app.add_route("/api/products", resources.ProductListResource())
    app.add_route("/api/products/search", resources.ProductSearchResource())
    app.add_route("/api/epeykatfg/monthly-inflation", resources.EpeyKatfgMonthlyResource())
    # compile=True on the final route forces the router decision tree to be
    # built at startup instead of lazily on the first request of each worker
    # (per Falcon docs: only set it on the LAST add_route call).
    app.add_route("/api/product", resources.ProductDetailResource(), compile=True)
    return app
