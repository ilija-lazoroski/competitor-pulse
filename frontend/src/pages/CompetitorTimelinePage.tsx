import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { listSnapshots, type PollOutcome, type Snapshot } from "../api";
import { changeLines, type NoteTone, summaryNote } from "../summaryNote";
import { timelineTone } from "../timeline";

const PAGE_SIZE = 50;

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" });

const NOTE_ICONS: Record<NoteTone, string> = {
  summary: "✦",
  info: "○",
  waiting: "◷",
  warning: "!",
};

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
  const [hasOlder, setHasOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSnapshots(null);
    setError(null);
    listSnapshots(id, PAGE_SIZE)
      .then((page) => {
        setSnapshots(page);
        setHasOlder(page.length === PAGE_SIZE);
      })
      .catch((err: Error) => setError(err.message));
  }, [id]);

  async function loadOlder() {
    const oldest = snapshots?.at(-1);
    if (!oldest) {
      return;
    }
    setLoadingOlder(true);
    try {
      const page = await listSnapshots(id, PAGE_SIZE, oldest.id);
      setSnapshots((loaded) => [...(loaded ?? []), ...page]);
      setHasOlder(page.length === PAGE_SIZE);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingOlder(false);
    }
  }

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
        <ol className="timeline">
          {snapshots.map((snapshot) => (
            <SnapshotItem key={snapshot.id} snapshot={snapshot} />
          ))}
        </ol>
      )}
      {hasOlder && (
        <button className="button load-older" type="button" onClick={loadOlder} disabled={loadingOlder}>
          {loadingOlder ? "Loading…" : "Load older snapshots"}
        </button>
      )}
    </section>
  );
}

function SnapshotItem({ snapshot }: { snapshot: Snapshot }) {
  const outcome = OUTCOME_LABELS[snapshot.outcome];
  const hasListing = snapshot.outcome === "ok" || snapshot.outcome === "incomplete";

  return (
    <li className={`snapshot snapshot-${timelineTone(snapshot)}`}>
      <div className="snapshot-head">
        <time className="snapshot-time muted" dateTime={snapshot.fetchedAt}>
          {dateTime.format(new Date(snapshot.fetchedAt))}
        </time>
        {outcome && <span className={`badge badge-${snapshot.outcome}`}>{outcome}</span>}
        {snapshot.changed && <span className="badge badge-changed">Changed</span>}
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
      <ChangeList changes={snapshot.changes} />
      <SummaryLine snapshot={snapshot} />
    </li>
  );
}

function ChangeList({ changes }: { changes: Snapshot["changes"] }) {
  const lines = changeLines(changes);
  if (lines.length === 0) {
    return null;
  }
  return (
    <ul className="change-list">
      {lines.map((line) => (
        <li key={line.field} className="change">
          <span className="change-label">{line.label}</span>
          <span className="change-old">{line.old}</span>
          <span className="change-arrow" aria-label="changed to">
            →
          </span>
          <span className="change-new">{line.new}</span>
        </li>
      ))}
    </ul>
  );
}

function SummaryLine({ snapshot }: { snapshot: Snapshot }) {
  const note = summaryNote(snapshot);
  return (
    <p className={`note note-${note.tone}`}>
      <span className="note-icon" aria-hidden="true">
        {NOTE_ICONS[note.tone]}
      </span>
      {/* Plain text only: the summary comes from an LLM that read untrusted listing text. */}
      <span>{note.text}</span>
    </p>
  );
}
