import type { ChangeView, ListingField, Snapshot } from "./api";

export type NoteTone = "summary" | "info" | "waiting" | "warning";

/** What a snapshot says about its change: the summary, or why there is none. */
export interface SummaryNote {
  tone: NoteTone;
  text: string;
}

export interface ChangeLine {
  field: ListingField;
  label: string;
  old: string;
  new: string;
}

const FIELD_LABELS: Record<ListingField, string> = {
  title: "Title",
  tagline: "Tagline",
  price: "Price",
  description: "Description",
};

const NONE = "none";

/**
 * Chooses the line to show under a snapshot.
 *
 * @param snapshot The snapshot, with its summary status and any summary error
 * @returns The summary itself, or a plain explanation of why there is none
 */
export function summaryNote(snapshot: Snapshot): SummaryNote {
  const reason = snapshot.summaryError ?? "no reason given";
  switch (snapshot.summaryStatus) {
    case "ready":
      return { tone: "summary", text: snapshot.summary ?? "" };
    case "no_change":
      return { tone: "info", text: "No change since the previous snapshot." };
    case "baseline":
      return { tone: "info", text: "First snapshot, so there is nothing to compare it with yet." };
    case "poll_failed":
      return { tone: "info", text: "No listing in this poll, so there is nothing to compare." };
    case "pending":
      return { tone: "waiting", text: "Change detected. The summary is being written." };
    case "llm_failed":
      return { tone: "warning", text: `Change detected, but the summary failed: ${reason}.` };
    case "llm_unusable":
      return {
        tone: "warning",
        text: `Change detected, but the LLM's answer could not be used: ${reason}.`,
      };
    case "cap_reached":
      return {
        tone: "warning",
        text: "Change detected, but there is no summary: the daily LLM limit was reached.",
      };
  }
}

/**
 * Lists a snapshot's changed fields as before and after, in the listing's order.
 *
 * @param changes The snapshot's changes, or null if nothing changed
 * @returns One line per changed field; a value that is not there reads "none"
 */
export function changeLines(changes: Snapshot["changes"]): ChangeLine[] {
  if (!changes) {
    return [];
  }
  return (Object.keys(FIELD_LABELS) as ListingField[]).flatMap((field) => {
    const change: ChangeView | undefined = changes[field];
    return change
      ? [{ field, label: FIELD_LABELS[field], old: change.old ?? NONE, new: change.new ?? NONE }]
      : [];
  });
}
