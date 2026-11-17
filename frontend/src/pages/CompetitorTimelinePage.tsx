import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { listSnapshots, type Snapshot } from "../api";

// Skeleton: shows how many snapshots the API returned for one competitor.
export function CompetitorTimelinePage() {
  const { id = "" } = useParams();
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSnapshots(id)
      .then(setSnapshots)
      .catch((err: Error) => setError(err.message));
  }, [id]);

  return (
    <section className="card">
      <Link to="/">← Back to competitors</Link>
      <h1>{id}</h1>
      {error && <p className="error">{error}</p>}
      <p>{snapshots.length} snapshots</p>
    </section>
  );
}
