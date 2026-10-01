import { describe, expect, it } from "vitest";

import { compareSyncStatusSeverity } from "./sync-status-severity";

describe("compareSyncStatusSeverity", () => {
  it("orders error-import, unknown, syncing, in-sync worst first", () => {
    // GIVEN
    const values = ["in-sync", "syncing", "error-import", "unknown"];

    // WHEN
    const sorted = [...values].sort(compareSyncStatusSeverity);

    // THEN
    expect(sorted).toEqual(["error-import", "unknown", "syncing", "in-sync"]);
  });

  it.each(["quarantined", null, undefined])("ranks %s with unknown", (value) => {
    expect(compareSyncStatusSeverity(value, "unknown")).toBe(0);
    expect(compareSyncStatusSeverity(value, "syncing")).toBeLessThan(0);
    expect(compareSyncStatusSeverity(value, "error-import")).toBeGreaterThan(0);
  });

  it("treats equal values as ties", () => {
    expect(compareSyncStatusSeverity("in-sync", "in-sync")).toBe(0);
  });
});
