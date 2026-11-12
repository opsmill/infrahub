import { describe, expect, it } from "vitest";

import { compareWorstSyncStatusFirst } from "@/entities/branch-git-status/domain/rules/sync-status-severity";

describe("compareWorstSyncStatusFirst", () => {
  it("orders error-import, unknown, syncing, in-sync worst first", () => {
    // GIVEN
    const values = ["in-sync", "syncing", "error-import", "unknown"];

    // WHEN
    const sorted = [...values].sort(compareWorstSyncStatusFirst);

    // THEN
    expect(sorted).toEqual(["error-import", "unknown", "syncing", "in-sync"]);
  });

  it.each(["quarantined", null, undefined])("ranks %s with unknown", (value) => {
    expect(compareWorstSyncStatusFirst(value, "unknown")).toBe(0);
    expect(compareWorstSyncStatusFirst(value, "syncing")).toBeLessThan(0);
    expect(compareWorstSyncStatusFirst(value, "error-import")).toBeGreaterThan(0);
  });

  it("treats equal values as ties", () => {
    expect(compareWorstSyncStatusFirst("in-sync", "in-sync")).toBe(0);
  });
});
