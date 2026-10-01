import { describe, expect, test } from "vitest";

import {
  type RepositoryCommitStatus,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import { getRepositoryCommitStatusQueryOptions } from "@/entities/repository/ui/queries/get-repository-commit-status.query";
import { REPOSITORY_COMMITS_POLL_INTERVAL_MS } from "@/entities/repository/ui/queries/get-repository-commits.query";

const PARAMS = { repositoryId: "repo-1", branchName: "main" };

function resolveRefetchInterval(status: RepositoryCommitStatus | undefined) {
  const { refetchInterval } = getRepositoryCommitStatusQueryOptions(PARAMS);
  if (typeof refetchInterval !== "function") {
    throw new Error("refetchInterval is expected to be a function");
  }
  return refetchInterval({ state: { data: status } } as Parameters<typeof refetchInterval>[0]);
}

describe("getRepositoryCommitStatusQueryOptions", () => {
  test("polls while the git state is unavailable", () => {
    // GIVEN
    const status = { condition: RepositoryGitCondition.UNAVAILABLE, pending_count: null };

    // WHEN
    const interval = resolveRefetchInterval(status);

    // THEN
    expect(interval).toBe(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
  });

  test("stops polling once a git state arrives", () => {
    // GIVEN
    const status = { condition: RepositoryGitCondition.BEHIND, pending_count: 2 };

    // WHEN
    const interval = resolveRefetchInterval(status);

    // THEN
    expect(interval).toBe(false);
  });

  test("keys the cache by repository and branch, apart from the commit log", () => {
    // WHEN
    const { queryKey, refetchOnWindowFocus } = getRepositoryCommitStatusQueryOptions(PARAMS);

    // THEN
    expect(queryKey).toEqual(["repositories", "commitStatus", PARAMS]);
    expect(refetchOnWindowFocus).toBe(false);
  });
});
