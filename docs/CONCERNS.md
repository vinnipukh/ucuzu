# Concerns

## Data availability

The repository does not contain the raw data. API startup can succeed without a database, but data endpoints will be empty or fail depending on adapter fallback. Deployment automation should build and validate `data/prices.db` before starting traffic.

## Cross-repository releases

The data and web repositories must agree on retailer labels, product identity rules, date formats and generated inflation columns. Use a dated artifact and record the source commit/checksum.

## SQLite concurrency

Use read-only connections, WAL-compatible storage, bounded worker/thread settings and reusable per-thread readers. Do not rebuild the active database in place under production traffic.

## Payload size

Unfiltered history can be large. Preserve bounded defaults, gzip/ETag behavior, response caching and any precomputed artifact strategy.

## Contract drift

The TypeScript types, API resources, verifier and canonical contract must be updated together. The canonical contract is the source of truth.

## Security

CORS defaults are permissive for local development. Restrict origins in production, keep secrets out of Git and expose no write database URL unless a future write feature is explicitly designed.
