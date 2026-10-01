import { describe, expect, test } from "vitest";

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
});
