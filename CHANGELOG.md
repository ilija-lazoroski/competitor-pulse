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
  - `CP_DATABASE_CONNECT_TIMEOUT_SECONDS` (default `5`): how long opening
  one new connection may take.
  - `CP_DATABASE_POOL_TIMEOUT_SECONDS` (default `10`): how long a query
  waits for a free connection when all are busy.
  - `CP_DATABASE_PING_TIMEOUT_SECONDS` (default `5`): how long
  `/health/db` waits for the database.
  - `CP_DATABASE_RECONNECT_TIMEOUT_SECONDS` (default `300`): how long the
  pool keeps retrying in the background when the database is down.
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
  within `CP_DATABASE_PING_TIMEOUT_SECONDS`.
  - `GET /api/competitors`: the tracked competitors, with `createdAt`,
  `lastChangedAt` and `changedRecently` (a change within
  `CP_API_RECENT_CHANGE_HOURS`).
  - `POST /api/competitors` with `{"id": string}`: start tracking;
  `201 Created`, `409 Conflict` if already tracked. The id is not checked
  with the source: the first poll shows whether the source knows it. A
  removed competitor is tracked again with its history.
  - `DELETE /api/competitors/{id}`: stop tracking and keep the history;
  `204 No Content`, `404 Not Found` if not tracked.
  - `GET /api/competitors/{id}/snapshots`: newest first, paged with
  `?limit=` and `?before=<snapshot id>`; `404 Not Found` if not tracked.
  Each snapshot has the brief's fields (price formatted as `$29/mo`)
  plus `id`, `outcome`, `error`, `summaryStatus` and `summaryError`.
  - Competitor ids must be lowercase slugs (`a-z`, `0-9`, inner `-`, at
  most 64 characters), in the body and in the path; otherwise `422`.
- API settings: `CP_API_RECENT_CHANGE_HOURS` (default `24`),
  `CP_API_SNAPSHOTS_PAGE_SIZE` (default `50`) and
  `CP_API_SNAPSHOTS_MAX_PAGE_SIZE` (default `200`).
- Migration: the timeline index also covers `id`, for keyset paging.
- Prices have a unit (`seat`, or any short lowercase word; none for a flat
  price) and can be free: `Free`, `Free forever` and `$0/mo` are one free
  price with no currency or period. Shown as `$12/seat/mo` and `Free`.
  Migration: `price_unit` column and the matching checks.
- Listing parser (`poller/listing_source/listing_parser.py`): cleans the
  source's text noise (whitespace, `&nbsp;`, `&amp;`) and reads every price form
  the source sent while probing it (`$29/mo`, `USD 29 per month`, `€8 / seat /
  month`, `Free`, ...) into one value, with amounts always in cents. Fields that
  are missing, empty or unreadable are listed as missing.
- Source settings: `CP_SOURCE_BASE_URL` (default `http://localhost:4002`;
  `http://listing-source:4002` in Docker Compose) and
  `CP_SOURCE_TIMEOUT_SECONDS` (default `10`).
- Poller (`competitor_pulse_poller`, the `poller` service in Docker Compose):
  a separate process that polls every tracked competitor, most overdue
  first, and stores each poll as a snapshot (`ok`, `incomplete`,
  `not_found` or `failed`). One shared rate limiter spaces all requests;
  a 429 pauses every request for `Retry-After` and puts the competitor back
  in the queue without storing it. Failed polls are not retried early.
- Poller settings: `CP_POLLER_INTERVAL_SECONDS` (default `900`),
  `CP_POLLER_REQUESTS_PER_SECOND` (`4`), `CP_POLLER_MAX_IN_FLIGHT` (`50`),
  `CP_POLLER_CLAIM_BATCH_SIZE` (`10`), `CP_POLLER_IDLE_SECONDS` (`1`),
  `CP_POLLER_RATE_LIMITED_PAUSE_SECONDS` (`1`) and
  `CP_POLLER_MAX_RATE_LIMITED_PAUSE_SECONDS` (`60`).
- Migration: `competitors.next_poll_at`, the poll schedule. Adding or
  restoring a competitor makes it due at once; claiming moves it one
  interval ahead (`FOR UPDATE SKIP LOCKED`).
- Change detection (`poller/change_detection.py`), run while saving a poll
  under the competitor's lock: a different title, tagline, price or
  description than the latest earlier listing is a change (`changed`,
  `changes` with old and new values, `summary_status` `pending`, and the
  competitor's `last_changed_at`). Unreadable fields and failed polls never
  count as a change.
- LLM summaries: a summarizer runs next to the poller and asks an
  OpenAI-compatible Chat Completions API (the mock LLM by default, Ollama
  with `ollama.env` and the `ollama` compose profile, or any other with
  `CP_LLM_BASE_URL`) to summarize each pending change, newest first. Calls
  are reserved against `CP_LLM_DAILY_CAP` per UTC day in the new
  `llm_usage` table. Failures are retried up to `CP_LLM_MAX_ATTEMPTS` times
  and then stored as `llm_failed`; unusable answers as `llm_unusable`; when
  the cap is reached, waiting changes become `cap_reached`.
- LLM settings: `CP_LLM_BASE_URL`, `CP_LLM_MODEL`, `CP_LLM_API_KEY`,
  `CP_LLM_TIMEOUT_SECONDS`, `CP_LLM_MAX_ATTEMPTS`,
  `CP_LLM_RETRY_BACKOFF_SECONDS`, `CP_LLM_DAILY_CAP`, `CP_LLM_MAX_IN_FLIGHT`,
  `CP_LLM_MAX_SUMMARY_CHARS` and `CP_LLM_IDLE_SECONDS`.
- Prompt injection defences for the summaries: instructions that treat the
  listing as untrusted data; the change sent as JSON between
  `<listing_change>` markers that listing text cannot close; values cut at
  `CP_LLM_MAX_FIELD_CHARS` (default `1000`); `temperature` 0 and
  `CP_LLM_MAX_TOKENS` (default `150`); answers with links, Markdown, HTML or
  more than one line are stored as `llm_unusable`.
- Snapshots in the API have `changes`: each changed field's old and new
  value, formatted, so a change is visible without a summary.
- Frontend skeleton in `frontend/`: React with Vite, TypeScript and React
  Router, a typed client for the API, and placeholder pages for the
  competitor list and timeline. The `frontend` service in Docker Compose
  serves it on <http://localhost:3000> with nginx, which forwards `/api`
  to the API.

### Changed

- The stored LLM error records are named `SummaryTimeout`,
  `SummaryConnectionError`, `SummaryHttpError` and `SummaryUnusableAnswer`.

### Fixed

- A `.env` copied from `.env.example` pointed the poller in Docker Compose
  at `localhost` for the source and the LLM, so every poll failed; those
  lines are now commented out. A source or LLM on the host is reachable as
  `host.docker.internal`, on Linux too.

- Summaries from the mock LLM were all stored as `llm_unusable`: it echoes
  the prompt, and the `<listing_change>` markers counted as HTML. Our own
  markers no longer count; any other markup still makes an answer unusable.

- `alembic upgrade head` ignored the `.env` file at `CP_CONFIG_PATH` and
  only read `CP_DATABASE_URL` from the environment; it now reads both, like
  the API and the poller.

- `CP_SOURCE_TIMEOUT_SECONDS` and `CP_LLM_TIMEOUT_SECONDS` limited each read
  rather than the whole request, so a source or LLM that sent its answer
  slowly could hold a request far longer; they now bound the whole request,
  from connecting to the last byte.

- Saving a poll looked up the competitor's latest answered poll by walking
  the snapshots' primary key back through every competitor's rows, while
  holding the competitor's lock; it now uses the timeline index (about 10 ms
  down to 0.04 ms on 4 million snapshots).

- A 429 paused all polling for as long as its `Retry-After` asked, so a
  source answering `Retry-After: 86400` stopped every poll for a day; the
  pause is now at most `CP_POLLER_MAX_RATE_LIMITED_PAUSE_SECONDS`.

### Removed
### Security
