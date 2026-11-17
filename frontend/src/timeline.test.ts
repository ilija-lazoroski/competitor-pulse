import { describe, expect, it } from "vitest";

import type { PollOutcome, Snapshot } from "./api";
import { mergeNewestPage, type TimelineTone, timelineTone } from "./timeline";

function snapshot(outcome: PollOutcome, changed: boolean): Snapshot {
  return {
    id: 1,
    fetchedAt: "2026-09-10T12:00:00Z",
    outcome,
    error: null,
    title: null,
    tagline: null,
    price: null,
    description: null,
    changed,
    changes: null,
    summary: null,
    summaryStatus: "no_change",
    summaryError: null,
  };
}

describe("timelineTone", () => {
  it.each<[PollOutcome, boolean, TimelineTone]>([
    ["ok", true, "changed"],
    // Disappearing from the source is a change, not just a failed poll.
    ["not_found", true, "changed"],
    ["not_found", false, "failed"],
    ["failed", false, "failed"],
    ["incomplete", false, "incomplete"],
    ["ok", false, "quiet"],
  ])("%s, changed %s, is %s", (outcome, changed, tone) => {
    expect(timelineTone(snapshot(outcome, changed))).toBe(tone);
  });
});

describe("mergeNewestPage", () => {
  const PAGE_SIZE = 3;

  // Snapshots with these ids, newest (highest id) first.
  function page(...ids: number[]): Snapshot[] {
    return ids.map((id) => ({ ...snapshot("ok", false), id }));
  }

  function ids(snapshots: Snapshot[]): number[] {
    return snapshots.map((s) => s.id);
  }

  it("shows the newest page when nothing is loaded yet", () => {
    const merged = mergeNewestPage(null, page(9, 8, 7), PAGE_SIZE);

    expect(merged).toEqual({ snapshots: page(9, 8, 7), hasOlder: true });
  });

  it("puts new snapshots on top and keeps the older pages loaded", () => {
    const loaded = { snapshots: page(8, 7, 6, 5, 4, 3), hasOlder: true };

    const merged = mergeNewestPage(loaded, page(10, 9, 8), PAGE_SIZE);

    expect(ids(merged.snapshots)).toEqual([10, 9, 8, 7, 6, 5, 4, 3]);
    expect(merged.hasOlder).toBe(true);
  });

  it("replaces a shown snapshot with its fresh copy", () => {
    const pending = { ...page(8)[0]!, changed: true, summaryStatus: "pending" as const };
    const ready = { ...pending, summaryStatus: "ready" as const, summary: "The price dropped." };
    const loaded = { snapshots: [pending, ...page(7)], hasOlder: false };

    const merged = mergeNewestPage(loaded, [ready, ...page(7)], PAGE_SIZE);

    expect(merged).toEqual({ snapshots: [ready, ...page(7)], hasOlder: false });
  });

  it("starts over when the newest page does not reach what is shown", () => {
    // Snapshots 7 to 4 may exist between the two: showing both would hide them.
    const loaded = { snapshots: page(3, 2, 1), hasOlder: false };

    const merged = mergeNewestPage(loaded, page(10, 9, 8), PAGE_SIZE);

    expect(merged).toEqual({ snapshots: page(10, 9, 8), hasOlder: true });
  });
});
