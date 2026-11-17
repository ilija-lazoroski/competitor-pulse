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
- **PostgreSQL:** `competitors` (with each one's poll schedule, last change and last known
  listing), `snapshots` (one per poll, failed polls included) and `llm_usage` (LLM calls per day,
  for the cap). The one-shot **migrate** service brings the schema up to date with Alembic before
  the API and the poller start.
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

## Run without Docker

The backend needs Python 3.14 and [Poetry](https://python-poetry.org), plus a PostgreSQL, the
listing source and an LLM. The simplest is to start only those three with Compose and run the API
and the poller from the checkout:

```bash
docker compose up -d db listing-source mock-llm
export CP_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/competitor_pulse

poetry install
poetry run alembic upgrade head
poetry run competitor_pulse          # the API, on http://localhost:8080
poetry run competitor_pulse_poller   # in a second terminal: the poller, summarizer and cleaner
```

The source and the LLM default to `http://localhost:4002` and `http://localhost:4001/v1`, where
Compose publishes them; without Docker at all, start them with
`node assets/files/listing-source/listing-source-server.mjs` (Node.js 18 or later) and
`python3 assets/files/mock-llm/mock-llm-server.py`. For the UI, run the Vite dev server (see
[Frontend](#frontend)); it forwards `/api` to the API on port 8080.

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

Both views ask the API again every 15 seconds while the tab is visible, so new polls, and summaries
that were still pending, appear without a reload.

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
- **Reading the source.** The brief asks to treat the source as an outside website, so its formats
  were learned by probing it over HTTP, never from its `listings.json`: 1,240 requests over every
  competitor and version, with its noise, format variants, partial listings and errors switched on.
  That showed the same values in many forms (whitespace, `&nbsp;`, 39 strings for 10 prices) and
  the parser turns them into one: text is cleaned, and a price becomes an amount, a currency, a
  period and a unit (`seat`, or any short unit word; none for a flat price), with `Free` and `$0/mo`
  as one free price. Over all 1,240 responses, every competitor version parsed to exactly one
  listing. What the parser cannot read is never guessed: the field counts as missing and the poll
  as `incomplete`. We first had the unit as a fixed list (`flat`, `seat`) and kept it as text
  instead, because the evaluation uses other data that may have other units.
- **What counts as a change.** The parser first removes the source's noise (extra fields,
  whitespace, HTML entities, and the many ways to write a price), so two listings that differ only
  in those are equal. A change is then any different value in the title, tagline, price or
  description, compared with the last value the source sent for that field; prices compare as
  values, so `$29/mo` and `USD 29 per month` are the same. A field the source left out or sent
  unreadable is unknown, not removed, so an incomplete poll never counts as a change, and the next
  poll is still compared with the value read before it (each competitor keeps its last known
  listing for this); a failed poll does not count either, and does not reset the comparison. A
  competitor that disappears from the source, or comes back unchanged, is a change with a fixed
  summary, which costs no LLM call. Every other change waits for the LLM's summary. We considered a
  threshold for "small" edits (for example a one-word change in the description) and left it out:
  how much an edit matters is for the summary to say, not a string-similarity number we would have
  to tune.
- **The rate limit.** The source allows 5 requests per second for everything together, so one
  rate limiter in the poller spaces all requests evenly, at 4 per second by default for headroom.
  That is also why the poller is its own process, started exactly once, rather than a background
  task in the API, where every API worker would have started its own poller and its own limiter. A
  429 pauses every request for its `Retry-After`, and the competitor goes back in the queue without
  a snapshot, since the poll never happened. The source client never retries on its own: every
  retry spends the same shared budget, so a failed poll is stored as failed and the competitor waits
  for its next turn.
- **How the history is stored.** One `snapshots` row per poll, failed and incomplete polls
  included, because the timeline must show them. A row has the listing as typed columns (the price
  as amount, currency, period and unit) and the error, the changes and the LLM's error as `jsonb`
  checked by Pydantic models; check constraints keep each row consistent (for example, an `ok` poll
  has no error, and a summary exists exactly when its status is `ready`). Removing a competitor only
  marks it removed: polling stops, the history stays for its 90 days, and adding the same id again
  continues the same timeline. We considered storing each listing once per version, with polls as
  small rows pointing to it (smaller, see the production numbers below), and deleting history on
  removal; one row per poll maps one to one onto the API and keeps the code simple at this size.
- **Scheduling and running at the same time as the API.** Each competitor has a `next_poll_at`. The
  poller claims due competitors with `FOR UPDATE SKIP LOCKED` and moves their next poll one interval
  ahead in the same statement, so a competitor is never claimed twice, and a crash costs one missed
  poll, not a burst of repeats. Saving a poll locks the competitor's row: a poll of a competitor
  removed in the meantime is dropped, and two saves of the same competitor (possible when it is
  removed and added back while a poll is under way) run one after the other, so the second compares
  with the first and a change is never reported, or summarized, twice. Paging the timeline uses
  `(fetched_at, id)` as a cursor, so new polls arriving while a user pages never cause gaps or
  repeats.
- **The LLM and its daily cap.** A change is stored as `pending` before the LLM is asked, so a slow
  or failing LLM never loses a poll; the summarizer runs next to the poller and takes the newest
  changes first, because they matter most when there is a backlog. Each call is reserved against the
  cap in PostgreSQL first, in one statement, so the cap holds however many calls run at once; a
  failed call counts too. A failure is tried up to `CP_LLM_MAX_ATTEMPTS` times, then shown as
  `llm_failed` with the reason; an HTTP error that would fail the same way again (a 4xx such as a
  wrong key or an unknown model, but not 408 or 429) is not retried, so a misconfigured LLM does not
  spend the cap three times over; an unusable answer (empty, cut off or too long) is not retried and
  is shown as `llm_unusable`. When the cap is reached, every waiting change is shown as
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

## Left out on purpose

- **Authentication:** the brief has one internal user.
- **More than one poller:** it would need the rate limiter shared through PostgreSQL or Redis, and
  would not raise the source's limit (see the production numbers).
- **Early retries of failed polls:** a failed poll waits for its next turn, because every retry
  spends the shared request budget.
- **Polling by how often a competitor changes, one LLM call for several changes, monthly
  partitions:** the next steps in the production numbers.
- **A threshold for "small" changes:** see what counts as a change.
- **Retrying changes that hit the daily LLM cap:** the next day's budget goes to new changes; the
  old ones still show their old and new values.
- **Protection against an LLM outage:** every failed call counts against the daily cap, and a
  change whose calls all fail stays `llm_failed`. A long outage can therefore use up the day's cap
  on failed calls and lose the summaries of the changes made during it. The next step would be a
  circuit breaker that stops calling after a few failures in a row and tries again later, leaving
  the changes `pending` meanwhile.
- **Native clients for LLM APIs that are not OpenAI-compatible,** such as Anthropic's: one more
  `LlmClient` adapter (see ports and adapters).
- **Metrics and alerts,** for example on failed polls, the request rate and the LLM budget: the
  services write structured logs, but nothing collects them.
- **End-to-end browser tests:** the frontend has unit tests for its logic; the API and the
  repositories are tested in Python.
- **A cloud deployment** (a bonus point in the brief).

## AI tools

I used **Claude Code** (Claude Opus 5.5) throughout. I chose the tech stack and the architecture;
for each part it proposed a design, and I approved or changed it before any code was written.

One place where I changed what it proposed: **the repositories.** It first put the poller's methods
(claiming due competitors, saving polls) into the API's `CompetitorRepository`, arguing that saving
a poll touches both tables. I had it split into one repository per consumer: the API, the poller,
the summarizer and the cleaner each depend on their own port with only the methods they use. The
transaction argument did not hold, because a single method can still cover both tables; and the
split removed methods that each side must never call, and the API settings the poller had to pass in
only to build the shared repository.

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
