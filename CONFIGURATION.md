# Configuration

The backend is configured with `CP_*` environment variables, or with a `.env` file whose path is in `CP_CONFIG_PATH`. Invalid or missing values stop startup.

The options below are generated from the settings classes in `competitor_pulse/configuration.py`. Do not edit them by hand; after changing a setting run:

```bash
scripts/autogenerate-settings-docs.sh
```

<!-- options-start -->
## `CP_BIND_ADDRESS`

*Optional*, default value: `127.0.0.1`

The interface to listen on

## `CP_PORT`

*Optional*, default value: `8080`

The port to listen on

## `CP_DEBUG`

*Optional*, default value: `False`

Enable debug mode (also override the log level)

## `CP_ENABLE_HOT_RELOAD`

*Optional*, default value: `False`

Enable hot-reloading during development

## `CP_LOG_DIRECTORY`

*Optional*, default value: `None`

The directory to write log files to (it will be created if it does not exist)

## `CP_LOG_LEVEL`

*Optional*, default value: `INFO`

The log level to use

### Possible values

`TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`

## `CP_WORKERS`

*Optional*, default value: `1`

The number of worker processes to spawn

## `CP_PRETTY_PRINT_LOGS`

*Optional*, default value: `True`

Enable pretty-printing of JSON logs

## `CP_SSL_CERTFILE`

*Optional*, default value: `None`

The path to the SSL certificate file

## `CP_SSL_KEYFILE`

*Optional*, default value: `None`

The path to the SSL key file

## `CP_DATABASE_URL`

**Required**

The connection string: postgresql://user:password@host/db

## `CP_DATABASE_POOL_MIN_SIZE`

*Optional*, default value: `2`

Connections the pool keeps open while idle

## `CP_DATABASE_POOL_MAX_SIZE`

*Optional*, default value: `10`

Most connections the pool opens

## `CP_DATABASE_CONNECT_TIMEOUT_SECONDS`

*Optional*, default value: `5`

How long opening one new connection may take

## `CP_DATABASE_POOL_TIMEOUT_SECONDS`

*Optional*, default value: `10`

How long a query waits for a free connection when all are busy

## `CP_DATABASE_PING_TIMEOUT_SECONDS`

*Optional*, default value: `5`

How long the database check (/health/db) waits for an answer

## `CP_DATABASE_RECONNECT_TIMEOUT_SECONDS`

*Optional*, default value: `300`

How long the pool keeps retrying in the background when the database cannot be reached, before it reports the failure and starts over

## `CP_API_RECENT_CHANGE_HOURS`

*Optional*, default value: `24`

A competitor counts as recently changed if its last change is this recent

## `CP_API_SNAPSHOTS_PAGE_SIZE`

*Optional*, default value: `50`

Snapshots per page when the request gives no limit

## `CP_API_SNAPSHOTS_MAX_PAGE_SIZE`

*Optional*, default value: `200`

Most snapshots a request may ask for (limit)

## `CP_SOURCE_BASE_URL`

*Optional*, default value: `http://localhost:4002/`

Where the listing source runs; listings come from <base_url>/listings/<id>

## `CP_SOURCE_TIMEOUT_SECONDS`

*Optional*, default value: `10`

How long one request to the source may take, from connecting to the last byte

## `CP_POLLER_INTERVAL_SECONDS`

*Optional*, default value: `900`

How often each competitor is polled; when the request budget is too small for this, every competitor falls behind evenly

## `CP_POLLER_REQUESTS_PER_SECOND`

*Optional*, default value: `4`

Most requests per second to the source, for all competitors together

## `CP_POLLER_MAX_IN_FLIGHT`

*Optional*, default value: `50`

Most requests to the source waiting for an answer at once

## `CP_POLLER_CLAIM_BATCH_SIZE`

*Optional*, default value: `10`

How many due competitors the poller takes at a time

## `CP_POLLER_IDLE_SECONDS`

*Optional*, default value: `1`

How long the poller waits when no competitor is due

## `CP_POLLER_RATE_LIMITED_PAUSE_SECONDS`

*Optional*, default value: `1`

How long to pause all requests after a 429 without a usable Retry-After

## `CP_POLLER_MAX_RATE_LIMITED_PAUSE_SECONDS`

*Optional*, default value: `60`

Longest pause after a 429, whatever its Retry-After asks for, so a source that asks for hours cannot stop polling for that long

## `CP_CLEANER_RETENTION_DAYS`

*Optional*, default value: `90`

How long snapshots are kept, by when they were fetched

## `CP_CLEANER_INTERVAL_SECONDS`

*Optional*, default value: `3600`

How often the cleaner deletes what is older

## `CP_CLEANER_BATCH_SIZE`

*Optional*, default value: `10000`

Most snapshots deleted in one transaction, so each one stays short

## `CP_LLM_BASE_URL`

*Optional*, default value: `http://localhost:4001/v1`

The OpenAI-compatible API; requests go to <base_url>/chat/completions

## `CP_LLM_MODEL`

*Optional*, default value: `mock-llm`

The model to ask

## `CP_LLM_API_KEY`

*Optional*, default value: `None`

Sent as a bearer token, if the LLM needs one

## `CP_LLM_TIMEOUT_SECONDS`

*Optional*, default value: `60`

How long one call to the LLM may take, from connecting to the last byte

## `CP_LLM_MAX_ATTEMPTS`

*Optional*, default value: `3`

Calls per change before its summary counts as failed

## `CP_LLM_RETRY_BACKOFF_SECONDS`

*Optional*, default value: `2`

Wait before the next attempt, multiplied by the attempt

## `CP_LLM_DAILY_CAP`

*Optional*, default value: `2000`

Most LLM calls per UTC day, for all competitors

## `CP_LLM_MAX_IN_FLIGHT`

*Optional*, default value: `4`

Most LLM calls waiting for an answer at once

## `CP_LLM_MAX_SUMMARY_CHARS`

*Optional*, default value: `500`

Longer answers are unusable rather than stored

## `CP_LLM_MAX_TOKENS`

*Optional*, default value: `150`

Most tokens the LLM may write; a longer answer is cut off

## `CP_LLM_MAX_FIELD_CHARS`

*Optional*, default value: `1000`

Longer listing values are cut before they go into the prompt

## `CP_LLM_IDLE_SECONDS`

*Optional*, default value: `1`

How long the summarizer waits when no change is pending
<!-- options-end -->
