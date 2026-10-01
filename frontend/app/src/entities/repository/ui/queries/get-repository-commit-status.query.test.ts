import { describe, expect, test } from "vitest";

import { RepositoryGitCondition } from "@/entities/repository/domain/model/repository";
import { getRepositoryCommitStatusQueryOptions } from "@/entities/repository/ui/queries/get-repository-commit-status.query";

const PARAMS = { repositoryId: "repo-1", branchName: "main" };

describe("getRepositoryCommitStatusQueryOptions", () => {
  test("reads once and leaves polling to the commit log", () => {
    // WHEN
    const options = getRepositoryCommitStatusQueryOptions(PARAMS);

    // THEN
    expect(options.refetchInterval).toBeUndefined();
    expect(options.refetchOnWindowFocus).toBe(false);
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
    const known = { condition: RepositoryGitCondition.BEHIND, pending_count: 2 };
    const cold = { condition: RepositoryGitCondition.UNAVAILABLE, pending_count: null };

    // WHEN
    const shared = typeof structuralSharing === "function" && structuralSharing(known, cold);

    // THEN
    expect(shared).toBe(known);
  });

  test("takes a new available status over a known one", () => {
    // GIVEN
    const { structuralSharing } = getRepositoryCommitStatusQueryOptions(PARAMS);
    const known = { condition: RepositoryGitCondition.BEHIND, pending_count: 2 };
    const next = { condition: RepositoryGitCondition.IN_SYNC, pending_count: null };

    // WHEN
    const shared = typeof structuralSharing === "function" && structuralSharing(known, next);

    // THEN
    expect(shared).toEqual(next);
  });
});
