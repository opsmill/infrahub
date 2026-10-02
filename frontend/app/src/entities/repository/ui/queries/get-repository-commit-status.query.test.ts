import { describe, expect, test } from "vitest";

import {
  type RepositoryCommitStatus,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import {
  getRepositoryCommitStatusQueryOptions,
  REPOSITORY_COMMITS_POLL_INTERVAL_MS,
} from "@/entities/repository/ui/queries/get-repository-commit-status.query";

const PARAMS = { repositoryId: "repo-1", branchName: "main" };

function resolveRefetchInterval(data: RepositoryCommitStatus | undefined) {
  const { refetchInterval } = getRepositoryCommitStatusQueryOptions(PARAMS);
  if (typeof refetchInterval !== "function") {
    throw new Error("refetchInterval is expected to be a function");
  }
  return refetchInterval({ state: { data } } as Parameters<typeof refetchInterval>[0]);
}

function unavailableStatus(reason: RepositoryGitUnavailableReason | null): RepositoryCommitStatus {
  return {
    condition: RepositoryGitCondition.UNAVAILABLE,
    pending_count: null,
    unavailable: reason === null ? null : { reason },
  };
}

describe("getRepositoryCommitStatusQueryOptions", () => {
  test("does not refetch on window focus", () => {
    // WHEN
    const { refetchOnWindowFocus } = getRepositoryCommitStatusQueryOptions(PARAMS);

    // THEN
    expect(refetchOnWindowFocus).toBe(false);
  });

  test.each([
    RepositoryGitUnavailableReason.NOT_CLONED,
    RepositoryGitUnavailableReason.TIMEOUT,
    null,
  ])("polls while the status is unavailable with reason %s", (reason) => {
    // WHEN
    const interval = resolveRefetchInterval(unavailableStatus(reason));

    // THEN
    expect(interval).toBe(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
  });

  test("does not poll when reading commits is not implemented", () => {
    // WHEN
    const interval = resolveRefetchInterval(
      unavailableStatus(RepositoryGitUnavailableReason.NOT_IMPLEMENTED)
    );

    // THEN
    expect(interval).toBe(false);
  });

  test.each([
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.BEHIND,
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.NOT_TRACKED,
  ])("does not poll once the status answers %s", (condition) => {
    // WHEN
    const interval = resolveRefetchInterval({ condition, pending_count: null, unavailable: null });

    // THEN
    expect(interval).toBe(false);
  });

  test("does not poll before any status has arrived", () => {
    // WHEN
    const interval = resolveRefetchInterval(undefined);

    // THEN
    expect(interval).toBe(false);
  });

  test("keys the cache by repository and branch, apart from the commit log", () => {
    // WHEN
    const { queryKey } = getRepositoryCommitStatusQueryOptions(PARAMS);

    // THEN
    expect(queryKey).toEqual(["repositories", "commitStatus", PARAMS]);
  });

  test("keeps a known status when a refresh answers unavailable", () => {
    // GIVEN
    const { structuralSharing } = getRepositoryCommitStatusQueryOptions(PARAMS);
    const known = { condition: RepositoryGitCondition.BEHIND, pending_count: 2, unavailable: null };
    const cold = unavailableStatus(RepositoryGitUnavailableReason.NOT_CLONED);

    // WHEN
    const shared = typeof structuralSharing === "function" && structuralSharing(known, cold);

    // THEN
    expect(shared).toBe(known);
  });

  test("takes a new available status over a known one", () => {
    // GIVEN
    const { structuralSharing } = getRepositoryCommitStatusQueryOptions(PARAMS);
    const known = { condition: RepositoryGitCondition.BEHIND, pending_count: 2, unavailable: null };
    const next = {
      condition: RepositoryGitCondition.IN_SYNC,
      pending_count: null,
      unavailable: null,
    };

    // WHEN
    const shared = typeof structuralSharing === "function" && structuralSharing(known, next);

    // THEN
    expect(shared).toEqual(next);
  });
});
