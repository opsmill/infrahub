import { describe, expect, test } from "vitest";

import {
  REPOSITORY_COMMIT_STATE,
  REPOSITORY_GIT_CONDITION,
  REPOSITORY_GIT_UNAVAILABLE_REASON,
  type RepositoryCommit,
  type RepositoryCommitLog,
  type RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import {
  getRepositoryCommitsQueryOptions,
  REPOSITORY_COMMITS_PAGE_SIZE,
  REPOSITORY_COMMITS_POLL_INTERVAL_MS,
} from "@/entities/repository/ui/queries/get-repository-commits.query";

const PARAMS = { repositoryId: "repo-1", branchName: "main" };

function buildCommit(index: number): RepositoryCommit {
  return {
    id: `commit-${index}`,
    __typename: "RepositoryCommit",
    hash: `${index}`.padStart(40, "0"),
    shortHash: `${index}`.padStart(7, "0"),
    summary: `Commit ${index}`,
    authorName: "Ada",
    authoredAt: "2026-01-01T00:00:00Z",
    state: REPOSITORY_COMMIT_STATE.HISTORY,
  };
}

function buildLog(condition: RepositoryGitCondition, commitCount = 1): RepositoryCommitLog {
  return {
    ...PARAMS,
    gitRef: "main",
    condition,
    importedCommit: null,
    remoteHead: null,
    pendingCount: null,
    fetchedAt: null,
    checkedAt: null,
    unavailable:
      condition === REPOSITORY_GIT_CONDITION.UNAVAILABLE
        ? { reason: REPOSITORY_GIT_UNAVAILABLE_REASON.NOT_CLONED, message: "not cloned" }
        : null,
    commits: Array.from({ length: commitCount }, (_, index) => buildCommit(index)),
  };
}

function resolveRefetchInterval(pages: RepositoryCommitLog[] | undefined) {
  const { refetchInterval } = getRepositoryCommitsQueryOptions(PARAMS);
  if (typeof refetchInterval !== "function") {
    throw new Error("refetchInterval is expected to be a function");
  }
  const data = pages && { pages, pageParams: pages.map(() => 0) };
  return refetchInterval({ state: { data } } as Parameters<typeof refetchInterval>[0]);
}

describe("getRepositoryCommitsQueryOptions", () => {
  test("polls while the first page is still unavailable", () => {
    // GIVEN
    const pages = [buildLog(REPOSITORY_GIT_CONDITION.UNAVAILABLE)];

    // WHEN
    const interval = resolveRefetchInterval(pages);

    // THEN
    expect(interval).toBe(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
  });

  test("stops polling once the first page carries a git state", () => {
    // GIVEN
    const pages = [buildLog(REPOSITORY_GIT_CONDITION.BEHIND)];

    // WHEN
    const interval = resolveRefetchInterval(pages);

    // THEN
    expect(interval).toBe(false);
  });

  test("does not poll before any data has arrived", () => {
    // GIVEN
    const pages = undefined;

    // WHEN
    const interval = resolveRefetchInterval(pages);

    // THEN
    expect(interval).toBe(false);
  });

  test("requests the next offset when the last page is full", () => {
    // GIVEN
    const { getNextPageParam } = getRepositoryCommitsQueryOptions(PARAMS);
    const lastPage = buildLog(REPOSITORY_GIT_CONDITION.IN_SYNC, REPOSITORY_COMMITS_PAGE_SIZE);

    // WHEN
    const nextOffset = getNextPageParam(lastPage, [lastPage], 0, [0]);

    // THEN
    expect(nextOffset).toBe(REPOSITORY_COMMITS_PAGE_SIZE);
  });

  test("stops paging when the last page is short", () => {
    // GIVEN
    const { getNextPageParam } = getRepositoryCommitsQueryOptions(PARAMS);
    const lastPage = buildLog(REPOSITORY_GIT_CONDITION.IN_SYNC, REPOSITORY_COMMITS_PAGE_SIZE - 1);

    // WHEN
    const nextOffset = getNextPageParam(lastPage, [lastPage], 0, [0]);

    // THEN
    expect(nextOffset).toBeUndefined();
  });

  test("keys the cache by repository, branch and page size", () => {
    // GIVEN
    const params = { repositoryId: "repo-42", branchName: "feature" };

    // WHEN
    const { queryKey } = getRepositoryCommitsQueryOptions(params);

    // THEN
    expect(queryKey).toEqual([
      "repositories",
      "commits",
      { ...params, limit: REPOSITORY_COMMITS_PAGE_SIZE },
    ]);
  });

  test("does not replay every loaded page on window focus", () => {
    // GIVEN
    const params = { repositoryId: "repo-42", branchName: "feature" };

    // WHEN
    const { refetchOnWindowFocus } = getRepositoryCommitsQueryOptions(params);

    // THEN
    expect(refetchOnWindowFocus).toBe(false);
  });
});
