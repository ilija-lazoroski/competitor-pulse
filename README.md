# Competitor Pulse

## Configuration

Configure the backend before anything else: it does not start until its required settings are
set. Settings come from `CP_*` environment variables, or from a `.env` file whose path is in
`CP_CONFIG_PATH`.

All options, with their defaults and which ones are required, are listed in
[CONFIGURATION.md](CONFIGURATION.md).
```

Or start from the example file, which has the local development values:

```bash
cp .env.example .env
export CP_CONFIG_PATH=.env
```

## Run with Docker

```bash
docker compose up --build
```

This starts PostgreSQL, runs the migrations (`alembic upgrade head`) once, then starts the API on
<http://localhost:8080>, the poller, the listing source on <http://localhost:4002> and the mock LLM
on <http://localhost:4001>. The poller is a separate process and must run only once, because it
owns the source's rate limit. Compose sets the database URL for the API itself; other settings come from
`.env` if it exists. If port 5432 is taken on your machine, set `POSTGRES_PORT`, for example
`POSTGRES_PORT=55432 docker compose up --build`.

## Tests

```bash
poetry run pytest
```

The database tests need a PostgreSQL server where they can create databases; each test gets a new
database and drops it afterwards. Without `CP_TEST_DATABASE_URL` they are skipped:

```bash
docker compose up -d db
CP_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres poetry run pytest
```

## Decisions

- **Adding an id the source does not know.** Any valid id is accepted without asking the source.
  The source answers `404` both for ids it does not know and for competitors that are delisted
  for now, so a check when adding could not tell them apart; it would also put a slow,
  rate-limited source in the path of the request. The first poll records `not_found`, and the
  timeline shows it. A typo is therefore noticed after the first poll, not when it is added.
- **What counts as a change.** The parser first removes the source's noise (extra fields,
  whitespace, HTML entities, and the many ways to write a price), so two listings that differ only
  in those are equal. A change is then any different value in the title, tagline, price or
  description, compared with the competitor's latest earlier listing; prices compare as values, so
  `$29/mo` and `USD 29 per month` are the same. A field the source left out or sent unreadable is
  unknown, not removed, so an incomplete poll never counts as a change; a failed poll does not
  either, and does not reset the comparison. A competitor that disappears from the source, or comes
  back unchanged, is a change with a fixed summary, which costs no LLM call. Every other change
  waits for the LLM's summary. We considered a threshold for "small" edits (for example a one-word
  change in the description) and left it out: how much an edit matters is for the summary to say,
  not a string-similarity number we would have to tune.

## Development setup

Install [pre-commit](https://pre-commit.com) once per machine, then enable the hooks in each clone:

```bash
pipx install pre-commit   # or: brew install pre-commit
pre-commit install        # installs the pre-commit, prepare-commit-msg and commit-msg hooks
```

If `pre-commit install` refuses because `core.hooksPath` is set (e.g. by the old commit-guard tool),
remove the global hook path first:

```bash
git config --global --unset core.hooksPath
```
