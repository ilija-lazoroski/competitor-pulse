// The backend's API, typed after its JSON. Every call goes to this app's own origin: the Vite dev
// server and nginx forward /api to the backend.

export type PollOutcome = "ok" | "incomplete" | "not_found" | "failed";

export type SummaryStatus =
  | "ready"
  | "no_change"
  | "baseline"
  | "poll_failed"
  | "pending"
  | "llm_failed"
  | "llm_unusable"
  | "cap_reached";

export type ListingField = "title" | "tagline" | "price" | "description";

export interface Competitor {
  id: string;
  createdAt: string;
  lastChangedAt: string | null;
  changedRecently: boolean;
}

export interface ChangeView {
  old: string | null;
  new: string | null;
}

export interface Snapshot {
  id: number;
  fetchedAt: string;
  outcome: PollOutcome;
  error: string | null;
  title: string | null;
  tagline: string | null;
  price: string | null;
  description: string | null;
  changed: boolean;
  changes: Partial<Record<ListingField, ChangeView>> | null;
  summary: string | null;
  summaryStatus: SummaryStatus;
  summaryError: string | null;
}

/** An answer from the API other than success, with the message to show. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export function listCompetitors(): Promise<Competitor[]> {
  return request("/api/competitors");
}

export function addCompetitor(id: string): Promise<void> {
  return request("/api/competitors", { method: "POST", body: JSON.stringify({ id }) });
}

export function removeCompetitor(id: string): Promise<void> {
  return request(`/api/competitors/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function listSnapshots(id: string, limit: number, before?: number): Promise<Snapshot[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (before !== undefined) {
    query.set("before", String(before));
  }
  return request(`/api/competitors/${encodeURIComponent(id)}/snapshots?${query}`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "message" in body && typeof body.message === "string") {
      return body.message;
    }
  } catch {
    // Not JSON, like a proxy's error page.
  }
  return `The server answered with HTTP ${response.status}`;
}
