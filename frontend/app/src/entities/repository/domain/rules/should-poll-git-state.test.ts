import { describe, expect, test } from "vitest";

import {
  type RepositoryCommitStatus,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { shouldPollGitState } from "@/entities/repository/domain/rules/should-poll-git-state";

function unavailableStatus(
  reason: RepositoryGitUnavailableReason | null
): Pick<RepositoryCommitStatus, "condition" | "unavailable"> {
  return {
    condition: RepositoryGitCondition.UNAVAILABLE,
    unavailable: reason === null ? null : { reason },
  };
}

describe("shouldPollGitState", () => {
  test.each([
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.BEHIND,
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.NOT_TRACKED,
  ])("%s is an answer, so it does not poll", (condition) => {
    expect(shouldPollGitState({ condition, unavailable: null })).toBe(false);
  });

  test.each([
    RepositoryGitUnavailableReason.NOT_CLONED,
    RepositoryGitUnavailableReason.TIMEOUT,
  ])("UNAVAILABLE with reason %s may resolve, so it polls", (reason) => {
    expect(shouldPollGitState(unavailableStatus(reason))).toBe(true);
  });

  test("UNAVAILABLE with reason NOT_IMPLEMENTED never resolves, so it does not poll", () => {
    expect(
      shouldPollGitState(unavailableStatus(RepositoryGitUnavailableReason.NOT_IMPLEMENTED))
    ).toBe(false);
  });

  test("UNAVAILABLE without a reason still polls", () => {
    expect(shouldPollGitState(unavailableStatus(null))).toBe(true);
  });
});
