import { describe, expect, test } from "vitest";

import { REPOSITORY_GIT_CONDITION } from "@/entities/repository/domain/model/repository";
import { getPendingImportCount } from "@/entities/repository/domain/rules/get-pending-import-count";

describe("getPendingImportCount", () => {
  test("BEHIND returns the pending count", () => {
    expect(
      getPendingImportCount({ condition: REPOSITORY_GIT_CONDITION.BEHIND, pendingCount: 3 })
    ).toBe(3);
  });

  test("BEHIND without a pending count returns null", () => {
    expect(
      getPendingImportCount({ condition: REPOSITORY_GIT_CONDITION.BEHIND, pendingCount: null })
    ).toBeNull();
  });

  test("IN_SYNC returns 0", () => {
    expect(
      getPendingImportCount({ condition: REPOSITORY_GIT_CONDITION.IN_SYNC, pendingCount: null })
    ).toBe(0);
  });

  test.each([
    REPOSITORY_GIT_CONDITION.REWRITTEN,
    REPOSITORY_GIT_CONDITION.ORPHANED,
    REPOSITORY_GIT_CONDITION.NO_REMOTE,
    REPOSITORY_GIT_CONDITION.NOT_TRACKED,
    REPOSITORY_GIT_CONDITION.UNAVAILABLE,
  ])("%s returns null", (condition) => {
    expect(getPendingImportCount({ condition, pendingCount: 5 })).toBeNull();
  });
});
