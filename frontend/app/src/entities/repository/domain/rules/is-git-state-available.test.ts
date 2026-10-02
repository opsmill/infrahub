import { describe, expect, test } from "vitest";

import {
  type RepositoryCommitLog,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";

function unavailableLog(
  reason: RepositoryGitUnavailableReason | null
): Pick<RepositoryCommitLog, "condition" | "unavailable"> {
  return {
    condition: RepositoryGitCondition.UNAVAILABLE,
    unavailable: reason === null ? null : { reason, message: "" },
  };
}

describe("isGitStateAvailable", () => {
  test.each([
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.BEHIND,
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.NOT_TRACKED,
  ])("%s carries a git state", (condition) => {
    expect(isGitStateAvailable({ condition })).toBe(true);
  });

  test.each([
    RepositoryGitUnavailableReason.NOT_CLONED,
    RepositoryGitUnavailableReason.NOT_IMPLEMENTED,
    RepositoryGitUnavailableReason.TIMEOUT,
  ])("UNAVAILABLE with reason %s carries no git state", (reason) => {
    expect(isGitStateAvailable(unavailableLog(reason))).toBe(false);
  });

  test("UNAVAILABLE without a reason carries no git state", () => {
    expect(isGitStateAvailable(unavailableLog(null))).toBe(false);
  });
});
