import { describe, expect, it } from "vitest";

import type { PollOutcome, Snapshot } from "./api";
import { type TimelineTone, timelineTone } from "./timeline";

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
