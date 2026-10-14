import { describe, expect, it } from "vitest";

import { getUnknownSyncStatus } from "@/entities/branch-git-status/domain/rules/get-unknown-sync-status";

describe("getUnknownSyncStatus", () => {
  it("takes the label, colour and description of the schema's unknown choice", () => {
    // GIVEN
    const choices = [
      { name: "in-sync", label: "In Sync", color: "#60a5fa", description: null },
      { name: "unknown", label: "Unknown", color: "#9ca3af", description: "Not synced yet" },
    ];

    // WHEN
    const status = getUnknownSyncStatus(choices);

    // THEN
    expect(status).toEqual({
      value: "unknown",
      label: "Unknown",
      color: "#9ca3af",
      description: "Not synced yet",
    });
  });

  it("keeps only the value when the schema has no unknown choice", () => {
    expect(getUnknownSyncStatus(undefined)).toEqual({
      value: "unknown",
      label: null,
      color: null,
      description: null,
    });
  });
});
