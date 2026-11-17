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

/** The snapshots shown on a timeline, newest first, and whether older ones can be loaded. */
export interface LoadedTimeline {
  snapshots: Snapshot[];
  hasOlder: boolean;
}

/**
 * Shows the first page of a timeline.
 *
 * @param page The newest snapshots, newest first
 * @param pageSize The page size that was asked for
 * @returns The timeline; a full page means there may be older snapshots
 */
export function firstPage(page: Snapshot[], pageSize: number): LoadedTimeline {
  return { snapshots: page, hasOlder: page.length === pageSize };
}

/**
 * Merges a fresh copy of the newest page into what is shown, keeping the older pages loaded.
 *
 * Snapshots already shown are replaced by their fresh copy (a pending summary may be ready now)
 * and new snapshots go on top. If the newest page shares no snapshot with what is shown, there
 * may be a gap between them, so the newest page replaces everything.
 *
 * @param loaded The timeline shown now; null if nothing loaded yet
 * @param newest The newest page, newest first, as just loaded
 * @param pageSize The page size that was asked for
 * @returns The timeline to show
 */
export function mergeNewestPage(
  loaded: LoadedTimeline | null,
  newest: Snapshot[],
  pageSize: number,
): LoadedTimeline {
  const newestIds = new Set(newest.map((snapshot) => snapshot.id));
  if (loaded === null || !loaded.snapshots.some((snapshot) => newestIds.has(snapshot.id))) {
    return firstPage(newest, pageSize);
  }
  return {
    snapshots: [...newest, ...loaded.snapshots.filter((snapshot) => !newestIds.has(snapshot.id))],
    hasOlder: loaded.hasOlder,
  };
}
