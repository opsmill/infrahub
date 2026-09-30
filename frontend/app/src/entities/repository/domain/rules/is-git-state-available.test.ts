import { describe, expect, test } from "vitest";

import {
  REPOSITORY_GIT_CONDITION,
  REPOSITORY_GIT_UNAVAILABLE_REASON,
  type RepositoryCommitLog,
  type RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";

function unavailableLog(
  reason: RepositoryGitUnavailableReason | null
): Pick<RepositoryCommitLog, "condition" | "unavailable"> {
  return {
    condition: REPOSITORY_GIT_CONDITION.UNAVAILABLE,
    unavailable: reason === null ? null : { reason, message: "" },
  };
}

describe("isGitStateAvailable", () => {
  test.each([
    REPOSITORY_GIT_CONDITION.IN_SYNC,
    REPOSITORY_GIT_CONDITION.BEHIND,
    REPOSITORY_GIT_CONDITION.REWRITTEN,
    REPOSITORY_GIT_CONDITION.ORPHANED,
    REPOSITORY_GIT_CONDITION.NO_REMOTE,
    REPOSITORY_GIT_CONDITION.NOT_TRACKED,
  ])("%s is an answer, so polling stops", (condition) => {
    expect(isGitStateAvailable({ condition })).toBe(true);
  });

  test.each([
    REPOSITORY_GIT_UNAVAILABLE_REASON.NOT_CLONED,
    REPOSITORY_GIT_UNAVAILABLE_REASON.NOT_IMPLEMENTED,
    REPOSITORY_GIT_UNAVAILABLE_REASON.TIMEOUT,
  ])("UNAVAILABLE with reason %s keeps polling", (reason) => {
    expect(isGitStateAvailable(unavailableLog(reason))).toBe(false);
  });

  test("UNAVAILABLE without a reason still keeps polling", () => {
    expect(isGitStateAvailable(unavailableLog(null))).toBe(false);
  });
});
