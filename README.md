# Competitor Pulse

CompetitorPulse is a system that tracks competitors' product listings over time.
It tracks a competitor listing from a configured source, storing it in a database, and decides
whether the listing changed in a way that matters to a product manager. For each change that
happened a configured LLM writes a short, plain-English summary.

A second part is a small React app that does bare minimum, lists the competitors, shows which
competitors' listings changed and in what way, their history as timeline and the summary of them.

## Architecture

![Architecture](docs/architecture.png)

- **frontend:** nginx serves the React app and forwards `/api` to the API, so the browser talks to
  one origin.
- **api:** Python FastAPI. It adds, removes and lists competitors and reads their snapshots.
- **poller** or scheduler is one process with three tasks, out of the API so it runs exactly once.
  If it were part of the API, every API worker would start its own poller, each with its own rate
  limiter, and together they would send more than the source allows.
  - **Poller:** claims the competitors that are due, fetches their listings at most 4 requests per
    second (because of production notes), decides whether each one changed and stores it as a snapshot.
  - **Summarizer:** asks the configured LLM to summarize each pending change, newest first, and stops
    at the daily LLM cap; the changes left are shown as `cap_reached`.
  - **Cleaner:** deletes history older than 90 days.
- **PostgreSQL:** `competitors` (with each one's poll schedule, last change and last known
  listing), `snapshots` (one per poll, failed polls included) and `llm_usage` (LLM calls per day,
  for the cap). Included is the migration service that uses Alembic to take care about schema
  management before the API and the poller start.
- **Listing source** which is an outside service that uses a configured service and gets back a
  listing for a competitor
- **The LLM** another outside service, any LLM with an OpenAI-compatible API, set by configuration.
  An API in another format, such as Anthropic's, would need its own `LLMClient` adapter.
- Both of above can be configured to local instances. (see [Point it at your own source and
  LLM](#point-it-at-your-own-source-and-llm)).

The code follows the [hexagonal architecture](https://devcookies.medium.com/a-detailed-guide-to-hexagonal-architecture-with-examples-042523acb1db) (ports and adapters). The logic of each part depends
only on **ports**: small `Protocol` classes that say what it needs from the outside world. An
**adapter** implements a port for one technology: PostgreSQL, HTTP, an LLM API. The logic never
imports an adapter; the composition roots, `app/dependencies.py` and `poller/main.py`, create the
adapters and hand them in.

| Port (`Protocol`) | Adapter | Used by | Replaced in tests by |
|---|---|---|---|
| `CompetitorRepository` | `PostgresCompetitorRepository` | the API's endpoints | `InMemoryCompetitorRepository` |
| `PollRepository` | `PostgresPollRepository` | the Poller | `SpyPollRepository` |
| `SummaryRepository` | `PostgresSummaryRepository` | the Summarizer | `InMemorySummaryRepository` |
| `RetentionRepository` | `PostgresRetentionRepository` | the Cleaner | `SpyRetentionRepository` |
| `ListingSource` | `HTTPListingSource` | the Poller | `SpyListingSource` |
| `LLMClient` | `OpenAILLMClient` | the Summarizer | `SpyLLM` |


## Configuration

Configuration is a big part of any service and it is written with idea in mind that many things
are going to be changed in future. With Docker nothing needs to be set first, because Compose sets
the database URL itself; without Docker this step needs to happen **before running the service**.
It includes required and optional settings, and it will not start unless all required settings
are set. There are two ways to set them: via environment file listing all environment variables
or setting them one by one in your session. Environment variables start with a prefix
of `CP_` which will separate them from any other settings. For setting up a environment file
you need to create the `.env` file and set single environment variable named `CP_CONFIG_PATH`
with the file path of the env file.

All options, with their defaults and which ones are required, are listed in
[CONFIGURATION.md](CONFIGURATION.md).

Or start from the example file, which has the local development values:

```bash
cp .env.example .env
export CP_CONFIG_PATH=.env
```

## Running the application with one command (Docker)

After configuration options are set, there is only one command that needs to be run:

```bash
docker compose up --build
```

This will build any needed Docker images and run the containers on your local machine.
What it does is: starting PostgreSQL along with the migrations (`alembic upgrade head`) once,
then starts the UI on <http://localhost:3000>, the API on <http://localhost:8080>, the poller,
the listing source on <http://localhost:4002> and the mock LLM (if not configured otherwise).
The poller is a separate process and it must be run only once, because it owns the listing source's
rate limit.

Compose sets the database URL for the API itself; other settings from `.env` if it exists, meaning
there we need only to have this file next to the compose file before running the command.

Note: If port 5432 is taken on your machine, set `POSTGRES_PORT`, for example
`POSTGRES_PORT=55432 docker compose up --build`.

## Running the application locally

The backend needs Python 3.14 and [Poetry](https://python-poetry.org) along with local instances of PostgreSQL, the
listing source and an LLM.

The simplest is to start only those three with Compose and run the API and the poller from the checkout,
with a mind that you have configured your project beforehand:

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

## Frontend

The React app is in `frontend/` (Vite, TypeScript, React Router). It needs Node 22.12 or newer.

In Docker, nginx serves it and forwards `/api` to the API; in
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
  CPU but writes loose summaries. You can switch it to a better one with `CP_LLM_MODEL`.
- **Your own LLM.** Point the poller at it, the same way as at your own listing source:

  ```bash
  CP_LLM_BASE_URL=https://your-llm.example/v1 CP_LLM_MODEL=your-model CP_LLM_API_KEY=... \
    docker compose up --build
  ```

  It has to speak the OpenAI Chat Completions API; Anthropic's own API, for example, would need
  its own client, which would be easy with the architecture of the service.

At most `CP_LLM_DAILY_CAP` calls (default 2,000) are made per UTC day; see
[CONFIGURATION.md](CONFIGURATION.md) for the timeouts, retries and the other settings.


## Decisions, decisions, decisions

I made the decisions in this project myself, starting with the tech stack and the architecture.

The tech stack is Python with FastAPI because I am mainly a Python engineer and that is where I can
show my work best. I used PostgreSQL with Alembic because I know them well. The UI reflects what I
have done mostly through my career. Docker is a must in every service I have built; without it the
service would not be ready to ship. I could have used AI more and written it in TypeScript, but it
would have taken more time than I had.

The [architecture](#architecture) is maybe slightly over-engineered for the task. I built it the way
I would want it if it had to scale and keep changing: independent components, so a change in one
does not change another, each easy to maintain. The poller runs as a single instance because the
source has one rate limit for everything and the limiter lives in the poller's memory; more pollers
would need it shared through PostgreSQL or Redis.

- **Reading the source**. In the instructions there was a point about the source being outside
  website on which we don't know much. Well I came to a decision first to learn about it and then
  use it like we do anything else in life. I probed it over HTTP instead of reading its `listings.json`: 1,240 requests across
  every competitor and version, with its noise, format variants, partial listings and errors
  switched on. The same values came back written in many ways, for example 39 different strings for
  10 prices, so the parser turns them into one form: cleaned text, and a price as amount, currency,
  period and unit, with `Free` and `$0/mo` as the same free price. I kept the unit as free text, not
  a fixed list, because the evaluation data may have other units. What we can't read is not
  guessed: the field counts as missing and the poll is stored as `incomplete`.
- **Adding an id the source does not know.** I accept any valid id without asking the source. The
  source answers `404` both for an unknown id and for a competitor that is delisted for now, so a
  check when adding could not tell the two apart, and adding would have to wait on a slow,
  rate-limited source. Instead the first poll records `not_found` and the timeline shows it, so a
  typo shows up after the first poll.
- **What counts as a change**. Based on what data we had I have decided to go with title, tagline,
  price or description. Each of these for me seems important as what would count as change. There
  could be a listing with same title but different price or different description meaning
  completely different thing. All of that needs to be caught. Before comparing, the parser removes
  the source's noise (whitespace, HTML entities, the many ways to write a price), so `$29/mo` and
  `USD 29 per month` are the same price. A field the source left out or sent unreadable is unknown,
  not removed, so an incomplete or failed poll is never a change. A competitor that disappears or
  comes back unchanged gets a fixed summary without an LLM call.
- **Error handling**. There are two types of errors. Exceptions are raised by the source and LLM
  clients while the poller handles them. Failure records are what gets stored with a snapshot and
  shown later: a failed poll on the timeline, a failed summary in place of the summary.
- **The rate limit.** The source based on production notes allows 5 requests per second for
  everything together, so the rate limiter in the poller spaces all requests evenly, at 4 per second
  by default. This is another reason why I have those as separate processes, rather than being a
  background task in the API, where every API worker would start its own. A 429 pauses every request
  for its `Retry-After` (capped by `CP_POLLER_MAX_RATE_LIMITED_PAUSE_SECONDS`), and the competitor goes back in the queue without a snapshot, since the poll
  never happened. The source client never retries on its own: every retry spends the same shared budget,
  so a failed poll is stored as failed and the competitor waits for its next turn.
- **Scheduling.** Each competitor has a `next_poll_at`. The poller claims the due ones with
  `FOR UPDATE SKIP LOCKED` and moves their next poll ahead in the same statement, so no competitor
  is claimed twice and a crash costs one missed poll. Saving a poll locks the competitor's row, so a
  poll of a competitor removed in the meantime is dropped, and two saves of the same competitor
  never both report the same change. The timeline pages by `(fetched_at, id)`, so new polls
  arriving while someone pages cause no gaps or repeats.
- **How the history is stored.** One `snapshots` row per poll, failed and incomplete polls are
  included, because I wanted to show them in the timeline. A row has the chosen columns as typed columns
  along with the error, the changes and the LLM's error validated by Pydantic. Removing a competitor
  only marks it removed: polling stops, the history stays for its 90 days (configurable) and
  adding it back again continues the same timeline.
- **The LLM and its daily cap.** A change is stored as `pending` first, so a slow or failing LLM
  never loses a poll. Each call is reserved against the cap in PostgreSQL before it is made, so the
  cap holds however many calls run at once, and failed calls count too. A failure is retried up to
  `CP_LLM_MAX_ATTEMPTS` times, except a 4xx such as a wrong key or an unknown model (but not 408 or
  429), which would only fail the same way again. An empty, cut-off or too long answer is not
  retried and is shown as `llm_unusable`. Either way, the API still returns each changed field's old
  and new value.
- **Listing text is untrusted.** I think security as a must and this was one thing that I didn't
  need to add but I wanted to. Since the listing can come from any source the text there could be
  malicious and I believe in zero trust, so I wanted to make sure we don't have any prompt injection
  or anything like that. The worst thing now that can happen is misleading summary but that is up to
  the user. The limit is done in three layers:
  1. The system message tells the model the listing is untrusted data to describe, never
     instructions, and asks for one or two plain sentences.
  2. The change is sent as JSON between `<listing_change>` markers, with `<` and `>` escaped
     inside, so the listing text cannot close the block or fake a new one. Each value is cut at
     `CP_LLM_MAX_FIELD_CHARS`.
  3. The answer is checked: `temperature` is 0, `max_tokens` is capped (`CP_LLM_MAX_TOKENS`), and
     an answer with a link, Markdown, HTML or more than one line is stored as `llm_unusable` and
     never shown. The UI shows summaries as plain text, next to the real old and new values.

  I tried it against `llama3.2:1b` with five injection attempts (ignore the instructions, a fake
  closing marker and system rule, a demanded link, a demanded Markdown list) and the model followed
  none of them. That lowers the risk; it does not guarantee anything.

## What doesn't fit in production
The brief's production context: 6,000 competitors, each polled every 15 minutes; at most 5
requests per second to the source; at most 2,000 LLM calls per day; 90 days of history. These do not
all fit together for sure.

**Polling: 6.7 requests per second are needed, 5 are allowed.** 6,000 competitors every 15 minutes
is 24,000 requests an hour, 6.7 per second. The poller sends at most `CP_POLLER_REQUESTS_PER_SECOND`
(4 by default, which leaves room under the source's 5), so a full round over 6,000 competitors takes
about 25 minutes. Nothing breaks: the poller always takes the most overdue competitors first, so
every competitor falls behind evenly instead of some never being polled, and a 429 pauses every
request rather than adding to the overload. Possible things to be considered are:

- **Poll by how often a competitor changes.** Most listings change rarely. A competitor whose last
  change is old can wait an hour; one that changed today, or that a user is looking at, comes back
  every 15 minutes. With most competitors stable, the busy ones get the 15 minutes the brief asks
  for within the same budget.
- **Ask the source for more.** A higher limit, a feed of changed ids, or conditional requests
  (`ETag`, `If-None-Match`) so an unchanged listing costs almost nothing. The provided source
  supports none of these.

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
PostgreSQL database, a snapshot takes about 290 bytes, about 480 with row overhead and the
indexes, so 90 days take about 15 GB: a normal size for PostgreSQL. The timeline reads one
competitor's newest snapshots through an index, so its speed does not depend on the table's size,
and the Cleaner deletes what is older than 90 days in short batches. What we would do next:

- **Monthly partitions.** Dropping a month is instant and leaves no work for vacuum, where deleting
  millions of rows does.
- **A listing once per version.** Most polls repeat the listing before them. Polls as small rows
  that point to a listing stored once per change would make the history about four times smaller.

## Left out on purpose
- **Authentication:** the brief has one internal user.
- **More than one poller:** it would need the rate limiter shared through PostgreSQL or Redis, and
  would not raise the source's limit (see [What doesn't fit in production](#what-doesnt-fit-in-production)).
- **Early retries of failed polls:** a failed poll waits for its next turn, because every retry
  spends the shared request budget.
- **Polling by how often a competitor changes, one LLM call for several changes, monthly
  partitions:** the next steps in [What doesn't fit in production](#what-doesnt-fit-in-production).
- **A threshold for "small" changes:** how much an edit matters is for the summary to say, not a
  similarity number we would have to tune.
- **Retrying changes that hit the daily LLM cap:** the next day's budget goes to new changes; the
  old ones still show their old and new values.
- **Protection against an LLM outage:** every failed call counts against the daily cap, and a
  change whose calls all fail stays `llm_failed`. A long outage can therefore use up the day's cap
  on failed calls and lose the summaries of the changes made during it. The next step would be a
  circuit breaker that stops calling after a few failures in a row and tries again later, leaving
  the changes `pending` meanwhile.
- **Native clients for LLM APIs that are not OpenAI-compatible,** such as Anthropic's: one more
  `LLMClient` adapter (see [Architecture](#architecture)).
- **Metrics and alerts,** for example on failed polls, the request rate and the LLM budget: the
  services write structured logs, but nothing collects them.
- **End-to-end browser tests:** the frontend has unit tests for its logic; the API and the
  repositories are tested in Python.
- **A cloud deployment** (a bonus point in the brief). I have few VMs online but those are already
  busy with personal projects and I didn't have time to do it next to them.


## AI tools
And this one is a must nowadays. I have used **Claude Code** personal on Pro with Opus 5.5 which
I use day-to-day and I already have all the skills I need. You can see through my GitHub
commit history what has been done in steps, some bigger than others.

If left out to Claude it would have done things very differently. Practically it proposed to use
TypeScript or Go but again that is not me. Over the time it made a lot of decisions that I didn't
agree on, but the worst one was when it tried to couple the repository we have for competitor
related logic and the poller process and its three tasks (poller, summarizer, cleaner). Next would be how it
defined the endpoints of the API. In my opinion, endpoints should have only one thing in them and
all the unrelated API logic should be in the other components like repositories. Third would be unit
tests, on which I have specific way of development and that is TDD which I want to follow whenever I
am given a chance. Written tests make better implementation if we know what to expect. There are
also other smaller bits, like the documentation which I wanted to be written in specific way, the
setup of the skeletons, and the structure of the code.

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
