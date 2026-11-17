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

## Which LLM

Summaries come from any LLM with an OpenAI-compatible Chat Completions API
(`POST <base URL>/chat/completions`). Three ways to run it:

- **The provided mock LLM (default).** `docker compose up --build` starts it and points the poller
  at it. It does not write real summaries; it echoes what it was sent, which shows that the call,
  the timeouts and the failure handling work.
- **Ollama, locally.** `docker compose --env-file ollama.env --profile ollama up --build` also
  starts Ollama, downloads `llama3.2:1b` once (about 1.3 GB) and uses it. The 1B model runs on a
  CPU but writes loose summaries; set `CP_LLM_MODEL` (in `ollama.env`) to a larger model, like
  `llama3.2:3b`, for better ones.
- **Your own LLM.** Point the poller at it, the same way as at your own listing source:

  ```bash
  CP_LLM_BASE_URL=https://your-llm.example/v1 CP_LLM_MODEL=your-model CP_LLM_API_KEY=... \
    docker compose up --build
  ```

  It has to speak the OpenAI Chat Completions API; Anthropic's own API, for example, would need
  its own client.

At most `CP_LLM_DAILY_CAP` calls (default 2,000) are made per UTC day; see
[CONFIGURATION.md](CONFIGURATION.md) for the timeouts, retries and the other settings.

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
- **The LLM and its daily cap.** A change is stored as `pending` before the LLM is asked, so a
  slow or failing LLM never loses a poll; the summarizer runs next to the poller and takes the
  newest changes first, because they matter most when there is a backlog. Each call is reserved
  against the cap in PostgreSQL first, in one statement, so the cap holds however many calls run
  at once; a failed call counts too. A failure is tried up to `CP_LLM_MAX_ATTEMPTS` times, then
  shown as `llm_failed` with the reason; an unusable answer (empty, cut off or too long) is not
  retried and is shown as `llm_unusable`. When the cap is reached, every waiting change is shown as
  `cap_reached`, and these are not retried the next day, so that day's budget goes to new changes.
  In every case the API returns the changed fields with their old and new values, so the user sees
  what changed even without a summary.
- **Listing text is untrusted.** It comes from competitors' websites and goes into the LLM's
  prompt, so it could try to instruct the model (prompt injection). The summary is only text: the
  LLM has no tools and sees no secrets, so the worst an attack can do is a misleading summary. We
  limit that in three layers:
  - **Instructions:** the system message says the listing is untrusted data to describe, never
    instructions, and asks for one or two plain sentences that state only what the data shows.
  - **Data that cannot pass for instructions:** the change is sent as JSON between
    `<listing_change>` markers, with every `<` and `>` inside escaped, so listing text cannot close
    the block or open a fake one; each value is cut at `CP_LLM_MAX_FIELD_CHARS`.
  - **Checked output:** `temperature` 0 and `max_tokens` (`CP_LLM_MAX_TOKENS`); an answer with a
    link, Markdown, HTML or more than one line is stored as `llm_unusable`, never shown. The UI shows
    summaries as plain text, next to the real old and new values.

  Tried against `llama3.2:1b` with five injection attempts (ignore the instructions, a fake closing
  marker and system rule, a demanded link, a demanded Markdown list): the model followed none of
  them. This lowers the risk; it does not guarantee a model never misbehaves.

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
