import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router";

import { addCompetitor, type Competitor, listCompetitors, removeCompetitor } from "../api";

// The same rule as the API's: lowercase letters, digits and inner dashes, at most 64 characters.
const COMPETITOR_ID = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function CompetitorListPage() {
  const [competitors, setCompetitors] = useState<Competitor[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    listCompetitors()
      .then((loaded) => {
        setCompetitors(loaded);
        setLoadError(null);
      })
      .catch((err: Error) => setLoadError(err.message));
  }, []);

  useEffect(load, [load]);

  return (
    <section className="card">
      <div>
        <h1>Competitors</h1>
        <p className="muted">Track a competitor's listing and see what changes over time.</p>
      </div>
      <TrackForm onTracked={load} />
      {loadError && <p className="error">{loadError}</p>}
      {competitors && <CompetitorList competitors={competitors} onRemoved={load} />}
    </section>
  );
}

function TrackForm({ onTracked }: { onTracked: () => void }) {
  const [id, setId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tracked, setTracked] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const competitorId = id.trim();
    setTracked(null);
    if (!COMPETITOR_ID.test(competitorId)) {
      setError("Use lowercase letters, digits and dashes, like acme-crm (at most 64 characters).");
      return;
    }
    setBusy(true);
    try {
      await addCompetitor(competitorId);
      setId("");
      setError(null);
      setTracked(competitorId);
      onTracked();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="track-form" onSubmit={submit}>
      <div className="track-row">
        <input
          className="input"
          value={id}
          onChange={(event) => setId(event.target.value)}
          placeholder="competitor id, e.g. acme-crm"
          aria-label="Competitor id"
          autoComplete="off"
          spellCheck={false}
        />
        <button className="button button-primary" type="submit" disabled={busy}>
          Track
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {tracked && (
        <p className="notice">
          Tracking <strong>{tracked}</strong>. Its first poll shows whether the source knows it.
        </p>
      )}
    </form>
  );
}

function CompetitorList({
  competitors,
  onRemoved,
}: {
  competitors: Competitor[];
  onRemoved: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function remove(id: string) {
    if (!window.confirm(`Stop tracking ${id}? Its history is kept.`)) {
      return;
    }
    try {
      await removeCompetitor(id);
      setError(null);
      onRemoved();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (competitors.length === 0) {
    return <p className="empty muted">No competitors tracked yet. Add one above.</p>;
  }

  return (
    <>
      {error && <p className="error">{error}</p>}
      <ul className="competitor-list">
        {competitors.map((competitor) => (
          <li key={competitor.id} className="competitor-row">
            <div className="competitor-main">
              <Link to={`/competitors/${competitor.id}`} className="competitor-id">
                {competitor.id}
              </Link>
              {competitor.changedRecently && (
                <span className="badge badge-changed">Changed in the last 24 h</span>
              )}
            </div>
            <span className="competitor-meta muted">
              {competitor.lastChangedAt
                ? `Last change ${dateTime.format(new Date(competitor.lastChangedAt))}`
                : "No change yet"}
            </span>
            <button
              className="button button-danger"
              type="button"
              onClick={() => remove(competitor.id)}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
