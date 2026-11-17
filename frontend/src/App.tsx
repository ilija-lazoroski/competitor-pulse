import { Link, Route, Routes } from "react-router";

import { CompetitorListPage } from "./pages/CompetitorListPage";
import { CompetitorTimelinePage } from "./pages/CompetitorTimelinePage";

export function App() {
  return (
    <main className="page">
      <header className="page-header">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          CompetitorPulse
        </Link>
      </header>
      <Routes>
        <Route path="/" element={<CompetitorListPage />} />
        <Route path="/competitors/:id" element={<CompetitorTimelinePage />} />
      </Routes>
    </main>
  );
}
