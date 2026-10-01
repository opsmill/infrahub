import { describe, expect, test } from "vitest";

import {
  type RepositoryCommit,
  type RepositoryCommitLog,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import {
  getRepositoryCommitsQueryOptions,
  REPOSITORY_COMMITS_PAGE_SIZE,
  REPOSITORY_COMMITS_POLL_INTERVAL_MS,
} from "@/entities/repository/ui/queries/get-repository-commits.query";

const PARAMS = { repositoryId: "repo-1", branchName: "main" };

function buildCommit(index: number): RepositoryCommit {
  return {
    hash: `${index}`.padStart(40, "0"),
    short_hash: `${index}`.padStart(7, "0"),
    summary: `Commit ${index}`,
    author_name: "Ada",
    authored_at: "2026-01-01T00:00:00Z",
    state: RepositoryCommitState.HISTORY,
  };
}

function buildLog(condition: RepositoryGitCondition, commitCount = 1): RepositoryCommitLog {
  return {
    repository_id: PARAMS.repositoryId,
    branch_name: PARAMS.branchName,
    git_ref: "main",
    condition,
    imported_commit: null,
    remote_head: null,
    pending_count: null,
    fetched_at: null,
    checked_at: null,
    unavailable:
      condition === RepositoryGitCondition.UNAVAILABLE
        ? { reason: RepositoryGitUnavailableReason.NOT_CLONED, message: "not cloned" }
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

function resolveStructuralSharing(
  oldPages: RepositoryCommitLog[] | undefined,
  newPages: RepositoryCommitLog[]
) {
  const { structuralSharing } = getRepositoryCommitsQueryOptions(PARAMS);
  if (typeof structuralSharing !== "function") {
    throw new Error("structuralSharing is expected to be a function");
  }
  const toData = (pages: RepositoryCommitLog[]) => ({
    pages,
    pageParams: pages.map((_, index) => index * REPOSITORY_COMMITS_PAGE_SIZE),
  });
  const oldData = oldPages && toData(oldPages);
  const newData = toData(newPages);
  return { oldData, newData, result: structuralSharing(oldData, newData) };
}

describe("getRepositoryCommitsQueryOptions", () => {
  test("keeps the loaded pages when a refetch answers unavailable", () => {
    // GIVEN
    const loaded = [
      buildLog(RepositoryGitCondition.IN_SYNC, REPOSITORY_COMMITS_PAGE_SIZE),
      buildLog(RepositoryGitCondition.IN_SYNC, 2),
    ];
    const cold = [buildLog(RepositoryGitCondition.UNAVAILABLE, 0)];

    // WHEN
    const { oldData, result } = resolveStructuralSharing(loaded, cold);

    // THEN
    expect(result).toBe(oldData);
  });

  test("takes the new pages when a refetch carries a git state", () => {
    // GIVEN
    const loaded = [buildLog(RepositoryGitCondition.IN_SYNC)];
    const fresh = [buildLog(RepositoryGitCondition.BEHIND)];

    // WHEN
    const { newData, result } = resolveStructuralSharing(loaded, fresh);

    // THEN
    expect(result).toEqual(newData);
  });

  test("takes the unavailable answer when nothing was loaded before", () => {
    // GIVEN
    const cold = [buildLog(RepositoryGitCondition.UNAVAILABLE, 0)];

    // WHEN
    const { newData, result } = resolveStructuralSharing(undefined, cold);

    // THEN
    expect(result).toEqual(newData);
  });

  test("takes a newer unavailable answer over an older one", () => {
    // GIVEN
    const notCloned = [buildLog(RepositoryGitCondition.UNAVAILABLE, 0)];
    const timedOut = [
      {
        ...buildLog(RepositoryGitCondition.UNAVAILABLE, 0),
        unavailable: { reason: RepositoryGitUnavailableReason.TIMEOUT, message: "timed out" },
      },
    ];

    // WHEN
    const { newData, result } = resolveStructuralSharing(notCloned, timedOut);

    // THEN
    expect(result).toEqual(newData);
  });

  test("polls while the first page is still unavailable", () => {
    // GIVEN
    const pages = [buildLog(RepositoryGitCondition.UNAVAILABLE)];

    // WHEN
    const interval = resolveRefetchInterval(pages);

    // THEN
    expect(interval).toBe(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
  });

  test("stops polling once the first page carries a git state", () => {
    // GIVEN
    const pages = [buildLog(RepositoryGitCondition.BEHIND)];

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
    const lastPage = buildLog(RepositoryGitCondition.IN_SYNC, REPOSITORY_COMMITS_PAGE_SIZE);

    // WHEN
    const nextOffset = getNextPageParam(lastPage, [lastPage], 0, [0]);

    // THEN
    expect(nextOffset).toBe(REPOSITORY_COMMITS_PAGE_SIZE);
  });

  test("stops paging when the last page is short", () => {
    // GIVEN
    const { getNextPageParam } = getRepositoryCommitsQueryOptions(PARAMS);
    const lastPage = buildLog(RepositoryGitCondition.IN_SYNC, REPOSITORY_COMMITS_PAGE_SIZE - 1);

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
