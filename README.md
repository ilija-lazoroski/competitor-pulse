# Competitor Pulse

CompetitorPulse tracks competitors' product listings over time. A poller fetches each tracked
competitor's listing from a listing source, keeps every poll as a snapshot, and decides whether the
listing changed in a way that matters to a product manager. For each such change an LLM writes a
short, plain-English summary. A small React app lists the competitors, shows which changed in the
last 24 hours, and shows each one's history as a timeline, with the summary or the reason there is
none.

## Architecture

![Architecture](docs/architecture.png)

The diagram's source is [docs/architecture.drawio](docs/architecture.drawio) (open it in draw.io).

- **frontend:** nginx serves the React app and forwards `/api` to the API, so the browser talks to
  one origin.
- **api:** FastAPI. It adds, removes and lists competitors and reads their snapshots, through the
  `CompetitorRepository`; it never calls the source or the LLM.
- **poller:** one process with three tasks, apart from the API so that it runs exactly once,
  whatever the API's number of workers: there is one rate limit for the source, and this process
  owns it.
  - **Poller:** claims the competitors that are due, fetches their listings at most 4 requests per
    second, decides whether each one changed and stores it as a snapshot.
  - **Summarizer:** asks the LLM to summarize each pending change, newest first, within the daily
    cap of LLM calls.
  - **Cleaner:** deletes history older than 90 days.
- **PostgreSQL:** `competitors` (with each one's poll schedule and last change), `snapshots` (one
  per poll, failed polls included) and `llm_usage` (LLM calls per day, for the cap). The one-shot
  **migrate** service brings the schema up to date with Alembic before the API and the poller start.
- **The listing source and the LLM** are outside services: Compose starts the provided ones, and
  the poller can be pointed at others (see [Point it at your own source and
  LLM](#point-it-at-your-own-source-and-llm)).

## Configuration

Configure the backend before anything else: it does not start until its required settings are
set. Settings come from `CP_*` environment variables, or from a `.env` file whose path is in
`CP_CONFIG_PATH`.

All options, with their defaults and which ones are required, are listed in
[CONFIGURATION.md](CONFIGURATION.md).

Or start from the example file, which has the local development values:

```bash
cp .env.example .env
export CP_CONFIG_PATH=.env
```

## Run with Docker

```bash
docker compose up --build
```

This starts PostgreSQL, runs the migrations (`alembic upgrade head`) once, then starts the UI on
<http://localhost:3000>, the API on <http://localhost:8080>, the poller, the listing source on <http://localhost:4002> and the mock LLM
on <http://localhost:4001>. The poller is a separate process and must run only once, because it
owns the source's rate limit. Compose sets the database URL for the API itself; other settings come from
`.env` if it exists. If port 5432 is taken on your machine, set `POSTGRES_PORT`, for example
`POSTGRES_PORT=55432 docker compose up --build`.

## Point it at your own source and LLM

Docker Compose starts the provided listing source and mock LLM, and the poller uses them unless
two settings say otherwise. Set them on the command line, or in a `.env` file next to
`docker-compose.yaml` (Compose reads it):

```bash
CP_SOURCE_BASE_URL=https://your-source.example \
CP_LLM_BASE_URL=https://your-llm.example/v1 \
docker compose up --build
```

- **Listing source:** `CP_SOURCE_BASE_URL` is the base URL; listings are read from
  `<CP_SOURCE_BASE_URL>/listings/<id>`. `CP_SOURCE_TIMEOUT_SECONDS` (default 10) is how long one
  request may take.
- **LLM:** `CP_LLM_BASE_URL` is an OpenAI-compatible API, usually ending in `/v1`; summaries are
  requested from `<CP_LLM_BASE_URL>/chat/completions`. Set `CP_LLM_MODEL` to the model to ask, and
  `CP_LLM_API_KEY` if it needs a key (sent as a bearer token). See [Which LLM](#which-llm).
- **An instance on the same machine as Docker:** inside the containers `localhost` is the
  container itself, so use `host.docker.internal` instead, for example
  `CP_SOURCE_BASE_URL=http://host.docker.internal:4002`; Compose maps that name on Linux too. A host
  firewall must let Docker's networks reach that port; when it does not, every poll fails with
  "The source did not answer within 10s".
- **Without Docker:** the same settings, as environment variables or in the file at
  `CP_CONFIG_PATH`.

The provided source and mock LLM still start, but nothing calls them. The timeline shows whether the
new instances answer: a poll the source does not answer is stored with the reason, and so is a
summary the LLM does not give.

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

## Frontend

The React app is in `frontend/` (Vite, TypeScript, React Router). It needs Node 22.12 or newer
(`frontend/.nvmrc` says 24). In Docker, nginx serves it and forwards `/api` to the API; in
development the Vite dev server does the same, to `http://localhost:8080` unless
`CP_FRONTEND_API_URL` says otherwise:

```bash
cd frontend
npm ci
npm run dev     # http://localhost:5173
npm test
```

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

### The production numbers

The brief's production context: 6,000 competitors, each polled every 15 minutes; at most 5
requests per second to the source; at most 2,000 LLM calls per day; 90 days of history. These do not
all fit together.

**Polling: 6.7 requests per second are needed, 5 are allowed.** 6,000 competitors every 15 minutes
is 24,000 requests an hour, 6.7 per second. The poller sends at most `CP_POLLER_REQUESTS_PER_SECOND`
(4 by default, which leaves room under the source's 5), so a full round over 6,000 competitors takes
about 25 minutes. Nothing breaks: the poller always takes the most overdue competitors first, so
every competitor falls behind evenly instead of some never being polled, and a 429 pauses every
request rather than adding to the overload. What we would do next:

- **Poll by how often a competitor changes.** Most listings change rarely. A competitor whose last
  change is old can wait an hour; one that changed today, or that a user is looking at, comes back
  every 15 minutes. With most competitors stable, the busy ones get the 15 minutes the brief asks
  for within the same budget.
- **Ask the source for more.** A higher limit, a feed of changed ids, or conditional requests
  (`ETag`, `If-None-Match`) so an unchanged listing costs almost nothing. The provided source
  supports none of these.
- More pollers would not help: the limit is the source's, for all of them together. Scaling out
  only makes sense for availability, with the rate limiter moved into PostgreSQL or Redis so that
  all pollers share it.

**LLM calls: 2,000 a day for up to 6,000 competitors.** Only changes that matter are summarized,
and a competitor that disappears or comes back unchanged gets a fixed summary without a call. Still,
if a third of the competitors changed every day, the cap would run out. When it does, the newest
changes have been summarized first, the rest show "the daily LLM limit was reached", and the
timeline still shows each changed field's old and new value, so nothing is hidden. What we would do
next:

- **One call per competitor, not per snapshot.** When several changes of one competitor wait, one
  summary can cover all of them.
- **Fixed summaries for simple changes.** A price that only went from $39/mo to $29/mo needs no
  LLM: "The price dropped from $39/mo to $29/mo." The LLM is for changes in text.
- **A cheaper or local model** where the cap is about cost: with Ollama the cap can go away.

**History: 90 days of every poll.** At 4 requests per second the poller makes about 346,000 polls a
day, so 90 days are about 31 million snapshots (39 million at the full 5 per second). Measured in
our database, a snapshot takes about 290 bytes, about 480 with PostgreSQL's row overhead and the
indexes, so 90 days take about 15 GB: a normal size for PostgreSQL. The timeline reads one
competitor's newest snapshots through an index, so its speed does not depend on the table's size,
and the Cleaner deletes what is older than 90 days in short batches. What we would do next:

- **Monthly partitions.** Dropping a month is instant and leaves no work for vacuum, where deleting
  millions of rows does.
- **A listing once per version.** Most polls repeat the listing before them. Polls as small rows
  that point to a listing stored once per change would make the history about four times smaller.

### Ports and adapters

The code follows the hexagonal architecture (ports and adapters). The logic of each part depends
only on **ports**: small `Protocol` classes that say what it needs from the outside world. An
**adapter** implements a port for one technology: PostgreSQL, HTTP, an LLM API. The logic never
imports an adapter; the composition roots, `app/dependencies.py` and `poller/main.py`, create the
adapters and hand them in.

| Port (`Protocol`) | Adapter | Used by | Replaced in tests by |
|---|---|---|---|
| `CompetitorRepository` | `PostgresCompetitorRepository` | the API's endpoints | `FakeCompetitorRepository` |
| `PollRepository` | `PostgresPollRepository` | the Poller | `FakePollRepository` |
| `SummaryRepository` | `PostgresSummaryRepository` | the Summarizer | `FakeSummaryRepository` |
| `RetentionRepository` | `PostgresRetentionRepository` | the Cleaner | `FakeRetentionRepository` |
| `ListingSource` | `HttpListingSource` | the Poller | `FakeListingSource` |
| `LlmClient` | `OpenAiLlmClient` | the Summarizer | `FakeLlm` |

Why this shape:

- **The outside world is the risky part.** The source is slow, flaky and rate limited; the LLM can
  be slow, fail or answer badly; both are swapped for other instances by the people evaluating
  this. Behind a port, each is one class with one job, and what goes wrong there arrives as our own
  errors (`SourceTimeoutError`, `ListingNotFoundError`, `LlmHttpError`, ...), never as an `httpx`
  exception. The API's repository does the same for its outcomes (`CompetitorNotTrackedError`,
  ...); a database that is down is the exception: its error is not wrapped, and is logged where the
  poller's tasks catch everything.
- **Logic is tested without the infrastructure.** The endpoints, the Poller, the Summarizer and the
  Cleaner run in their tests against in-memory fakes, so the tests check our decisions (a 429 is
  requeued, an unusable answer is not retried, the cap marks every waiting change) quickly, with no
  database or network. Each adapter has its own tests against what it really talks to: a real
  PostgreSQL, or an HTTP mock of the source and the LLM.
- **Adapters can be swapped.** The mock LLM, Ollama and any other OpenAI-compatible API are one
  adapter and a setting. A native client for another API, such as Anthropic's, would be one more
  `LlmClient` adapter; nothing that uses the port would change.
- **One port per consumer, not one per table.** The API, the Poller, the Summarizer and the Cleaner
  each have their own repository with only the methods they use, so none of them can call
  something meant for another (the API cannot claim polls; the poller cannot remove competitors).
  The four repositories share the same tables.
- **The repository owns the transaction.** Each method is one transaction with its own locking,
  for example `save_poll` locks the competitor, compares, inserts and sets the last change
  together. The callers stay free of SQL and of transactions.
- **HTTP stays at the edge.** Endpoints make one repository call each; the repository raises our
  errors, and only `app/api_error_handling.py` turns them into HTTP statuses.

Where we bent the pattern, on purpose:

- **The API's repository returns the API's models** (`Competitor`, `Snapshot` in `models.py`), with
  the price already formatted, instead of domain objects that the endpoint would map. With one API
  and one storage, the extra mapping layer would only repeat itself; a second API would bring it
  back.
- **Change detection runs inside `PostgresPollRepository.save_poll`.** The comparison itself is
  pure logic in `poller/change_detection.py`, but the repository calls it, because it has to run
  under the competitor's row lock: two saves of the same competitor must not both see "changed".
  A cleaner split would need the lock (a unit of work) to be part of the port.

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
