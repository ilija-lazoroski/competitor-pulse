import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { listSnapshots, type PollOutcome, type Snapshot } from "../api";

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" });

// Polls that went wrong get a label; a normal poll needs none.
const OUTCOME_LABELS: Record<PollOutcome, string | null> = {
  ok: null,
  incomplete: "Incomplete",
  not_found: "Not listed",
  failed: "Poll failed",
};

export function CompetitorTimelinePage() {
  const { id = "" } = useParams();
  const [snapshots, setSnapshots] = useState<Snapshot[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSnapshots(null);
    setError(null);
    listSnapshots(id)
      .then(setSnapshots)
      .catch((err: Error) => setError(err.message));
  }, [id]);

  return (
    <section className="card">
      <div>
        <Link to="/" className="button">
          ← Back to competitors
        </Link>
      </div>
      <h1>{id}</h1>
      {error && <p className="error">{error}</p>}
      {snapshots?.length === 0 && (
        <p className="empty muted">No snapshots yet. The first poll is on its way.</p>
      )}
      {snapshots && snapshots.length > 0 && (
        <ol className="snapshot-list">
          {snapshots.map((snapshot) => (
            <SnapshotItem key={snapshot.id} snapshot={snapshot} />
          ))}
        </ol>
      )}
    </section>
  );
}

function SnapshotItem({ snapshot }: { snapshot: Snapshot }) {
  const outcome = OUTCOME_LABELS[snapshot.outcome];
  const hasListing = snapshot.outcome === "ok" || snapshot.outcome === "incomplete";

  return (
    <li className={`snapshot snapshot-${snapshot.outcome}`}>
      <div className="snapshot-head">
        <time className="snapshot-time muted" dateTime={snapshot.fetchedAt}>
          {dateTime.format(new Date(snapshot.fetchedAt))}
        </time>
        {outcome && <span className={`badge badge-${snapshot.outcome}`}>{outcome}</span>}
      </div>
      {hasListing && (
        <div className="listing">
          <p className="listing-title">
            <strong>{snapshot.title ?? "No title"}</strong>
            {snapshot.tagline && <span className="muted"> — {snapshot.tagline}</span>}
          </p>
          {snapshot.price && <p className="listing-price">{snapshot.price}</p>}
          {snapshot.description && <p className="listing-description">{snapshot.description}</p>}
        </div>
      )}
      {snapshot.error && <p className="snapshot-error">{snapshot.error}</p>}
    </li>
  );
}
