# Changelog
All notable changes to this project will be documented in this
file.

The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]
### Added

- Configuration from `CP_*` environment variables, or from the `.env` file
  at `CP_CONFIG_PATH`. Invalid or missing values stop startup:
  - `CP_DATABASE_URL` (required): the PostgreSQL connection string,
  `postgresql://user:password@host:port/db`; kept secret in logs.
  - `CP_DATABASE_POOL_MIN_SIZE` (default `2`): connections the pool keeps
  open while idle.
  - `CP_DATABASE_POOL_MAX_SIZE` (default `10`): most connections the pool
  opens; must not be smaller than `CP_DATABASE_POOL_MIN_SIZE`.
  - From service-kit: `CP_BIND_ADDRESS` (default `127.0.0.1`), `CP_PORT`
  (`8080`), `CP_WORKERS` (`1`), `CP_ENABLE_HOT_RELOAD` (`false`),
  `CP_DEBUG` (`false`), `CP_LOG_LEVEL` (`INFO`), `CP_LOG_DIRECTORY`
  (none), `CP_PRETTY_PRINT_LOGS` (`true`), `CP_SSL_CERTFILE` and
  `CP_SSL_KEYFILE` (none).
- Endpoints:
  - `GET /health`: liveness check, `200 {"status": "ok"}` while the
  process is up; does not touch the database.
  - `GET /health/db`: runs `SELECT 1`; `200 {"status": "ok"}`, or
  `503 {"status": "unavailable"}` if the database does not answer
  within 5 seconds.
  - Stubs of the competitor API that answer `501 Not Implemented` for now:
  - `GET /api/competitors`: list tracked competitors.
  - `POST /api/competitors` with `{"id": string}`: start tracking a
  competitor (`201 Created` once implemented).
  - `DELETE /api/competitors/{id}`: stop tracking a competitor
  (`204 No Content` once implemented).
  - `GET /api/competitors/{id}/snapshots`: a competitor's snapshots,
  newest first.

### Changed
### Fixed
### Removed
### Security
