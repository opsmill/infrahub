import { describe, expect, test } from "vitest";

import { RepositoryGitCondition } from "@/entities/repository/domain/model/repository";
import { getPendingImportCount } from "@/entities/repository/domain/rules/get-pending-import-count";

describe("getPendingImportCount", () => {
  test("BEHIND returns the pending count", () => {
    expect(
      getPendingImportCount({ condition: RepositoryGitCondition.BEHIND, pending_count: 3 })
    ).toBe(3);
  });

  test("BEHIND without a pending count returns null", () => {
    expect(
      getPendingImportCount({ condition: RepositoryGitCondition.BEHIND, pending_count: null })
    ).toBeNull();
  });

  test("IN_SYNC returns 0", () => {
    expect(
      getPendingImportCount({ condition: RepositoryGitCondition.IN_SYNC, pending_count: null })
    ).toBe(0);
  });

  test.each([
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
    RepositoryGitCondition.REF_MISSING,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.NOT_TRACKED,
    RepositoryGitCondition.UNAVAILABLE,
  ])("%s returns null", (condition) => {
    expect(getPendingImportCount({ condition, pending_count: 5 })).toBeNull();
  });
});
