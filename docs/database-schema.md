# Database schema

Defined in `backend/app/models.py`; migration `backend/alembic/versions/0001_initial_schema.py` (tested upgrade
→ downgrade → upgrade on PostgreSQL 16). JSON columns are `JSONB` on PostgreSQL and `JSON` on SQLite.

TimescaleDB is **not** used: the full history of all sources is ~240k rows (~80 MB including cache), well within
plain PostgreSQL with the composite index below. It can be adopted later by converting `observations` to a
hypertable on `period_start` without application changes.

| Table | Purpose | Key columns |
|---|---|---|
| `sources` | Registry mirror + runtime health | `id` PK, `meta` (licence, limits, schedule, verification), `enabled`, `last_attempt_at`, `last_success_at`, `last_error`, `consecutive_failures` |
| `series` | Catalogue mirror + runtime metadata | `id` PK, `source_id` FK, `source_key`, `definition` (full catalogue entry), `source_title`, `last_period`, `release_date`, `next_release`, `last_retrieved_at`, `last_request_url`, `source_meta` (source page, bulletins, ONS versions, dim/geo labels) |
| `observations` | Every observation | `series_id` FK, `geo` (GSS), `dim` (`_` = total), `period`, `period_start`, `period_end`, `value` (nullable = missing), `status` (normal/provisional/forecast/suppressed/missing), `flags` (CI, CV, derived formula…), `release_date`, `retrieved_at`, `run_id` FK, `is_demo`. **Unique** (`series_id`, `geo`, `dim`, `period`, `is_demo`); index (`series_id`, `geo`, `dim`, `period_start`) |
| `observation_revisions` | Value changes detected between retrievals | `series_id`, `geo`, `dim`, `period`, `old_value`, `new_value`, `old_release_date`, `new_release_date`, `detected_at`, `run_id` |
| `ingestion_runs` | One row per run | `source_id`, `job` (scheduled/manual/cli), `status` (running/success/partial/failed/skipped), counts (`fetched`, `inserted`, `updated`, `revised`, `unchanged`), `errors` (per series), `requests` (every HTTP call), `message` |
| `alerts` | Deduplicated alerts | `fingerprint` unique, `kind`, `severity`, `series_id`, `source_id`, `geo`, `dim`, `period`, `title`, `detail`, `payload`, `active` |
| `geo_areas` | UK, nations, ITL1, LADs | `code` PK (GSS), `name`, `level`, `parent_code`, `alt_codes` (ITL code, Land Registry slug, lookup URL) |
| `geo_boundaries` | Generalised boundary GeoJSON | `level` PK, `geojson`, `source_url`, `retrieved_at`, `feature_count` |
| `saved_views` | Named page + filter states | `name`, `path`, `state` |
| `http_cache` | Raw responses for conditional requests / TTL caching | `key` (sha256), `url`, `status`, `etag`, `last_modified`, `body`, `fetched_at` |

Integrity guarantees enforced in code (`ingestion/runner.py`, `services.py`):
- Real and demo rows can coexist for one key only because `is_demo` is part of the unique key; the read path
  selects exactly one of them per series, never both.
- A failed run writes no observations and deletes nothing.
- History that a source stops returning is retained.
