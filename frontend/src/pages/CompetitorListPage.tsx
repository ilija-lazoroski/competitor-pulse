import { useEffect, useState } from "react";
import { Link } from "react-router";

import { type Competitor, listCompetitors } from "../api";

// Skeleton: lists the tracked competitors to show the API is wired up.
export function CompetitorListPage() {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCompetitors()
      .then(setCompetitors)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <section className="card">
      <h1>Competitors</h1>
      {error && <p className="error">{error}</p>}
      <ul>
        {competitors.map((competitor) => (
          <li key={competitor.id}>
            <Link to={`/competitors/${competitor.id}`}>{competitor.id}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
