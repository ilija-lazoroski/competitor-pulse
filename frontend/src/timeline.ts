import type { Snapshot } from "./api";

/** How a snapshot shows on the timeline: changes stand out, quiet polls step back. */
export type TimelineTone = "changed" | "failed" | "incomplete" | "quiet";

/**
 * Chooses a snapshot's dot on the timeline.
 *
 * @param snapshot The snapshot
 * @returns changed for a change that matters (disappearing from the source included), failed for
 *          a poll without a listing, incomplete for a listing with unreadable fields, quiet
 *          otherwise
 */
export function timelineTone(snapshot: Snapshot): TimelineTone {
  if (snapshot.changed) {
    return "changed";
  }
  if (snapshot.outcome === "failed" || snapshot.outcome === "not_found") {
    return "failed";
  }
  return snapshot.outcome === "incomplete" ? "incomplete" : "quiet";
}
