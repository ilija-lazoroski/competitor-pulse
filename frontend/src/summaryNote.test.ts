import { describe, expect, it } from "vitest";

import type { Snapshot, SummaryStatus } from "./api";
import { changeLines, summaryNote } from "./summaryNote";

function snapshot(fields: Partial<Snapshot>): Snapshot {
  return {
    id: 1,
    fetchedAt: "2026-09-10T12:00:00Z",
    outcome: "ok",
    error: null,
    title: "Acme CRM",
    tagline: null,
    price: "$29/mo",
    description: null,
    changed: true,
    changes: null,
    summary: null,
    summaryStatus: "pending",
    summaryError: null,
    ...fields,
  };
}

describe("summaryNote", () => {
  it("shows the summary when there is one", () => {
    const note = summaryNote(snapshot({ summaryStatus: "ready", summary: "Price dropped." }));

    expect(note).toEqual({ tone: "summary", text: "Price dropped." });
  });

  it.each<[SummaryStatus, string]>([
    ["no_change", "info"],
    ["baseline", "info"],
    ["poll_failed", "info"],
    ["pending", "waiting"],
    ["cap_reached", "warning"],
  ])("explains %s", (summaryStatus, tone) => {
    const note = summaryNote(snapshot({ summaryStatus }));

    expect(note.tone).toBe(tone);
    expect(note.text).not.toBe("");
  });

  it.each<SummaryStatus>(["llm_failed", "llm_unusable"])("gives the reason for %s", (status) => {
    const note = summaryNote(
      snapshot({ summaryStatus: status, summaryError: "The LLM answered with HTTP 500" }),
    );

    expect(note.tone).toBe("warning");
    expect(note.text).toContain("The LLM answered with HTTP 500");
  });
});

describe("changeLines", () => {
  it("lists the changed fields in the listing's order, with none for a missing value", () => {
    const lines = changeLines({
      description: { old: "Track leads.", new: "Track leads and deals." },
      price: { old: "$39/mo", new: "$29/mo" },
      tagline: { old: "Simple CRM", new: null },
    });

    expect(lines).toEqual([
      { field: "tagline", label: "Tagline", old: "Simple CRM", new: "none" },
      { field: "price", label: "Price", old: "$39/mo", new: "$29/mo" },
      { field: "description", label: "Description", old: "Track leads.", new: "Track leads and deals." },
    ]);
  });

  it("is empty when nothing changed", () => {
    expect(changeLines(null)).toEqual([]);
  });
});
