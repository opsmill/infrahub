import { describe, expect, it } from "vitest";

import { isFilterableSyncStatus } from "@/entities/repository/domain/model/repository";

describe("isFilterableSyncStatus", () => {
  it.each(["unknown", "in-sync", "error-import", "error-ref-missing", "syncing"])(
    "accepts %s",
    (value) => {
      // GIVEN
      const candidate: unknown = value;

      // WHEN
      const result = isFilterableSyncStatus(candidate);

      // THEN
      expect(result).toBe(true);
    }
  );

  it.each(["bogus", "", 42])("rejects %j", (value) => {
    // GIVEN
    const candidate: unknown = value;

    // WHEN
    const result = isFilterableSyncStatus(candidate);

    // THEN
    expect(result).toBe(false);
  });
});
