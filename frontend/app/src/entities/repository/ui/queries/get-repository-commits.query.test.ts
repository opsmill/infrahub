import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  type RepositoryCommit,
  type RepositoryCommitLog,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { getRepositoryCommits } from "@/entities/repository/domain/use-cases/get-repository-commits";
import { REPOSITORY_COMMITS_POLL_INTERVAL_MS } from "@/entities/repository/ui/queries/get-repository-commit-status.query";
import { getRepositoryCommitsQueryOptions } from "@/entities/repository/ui/queries/get-repository-commits.query";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_COMMITS_PAGE_SIZE,
  REPOSITORY_COMMITS_STALE_TIME_MS,
} from "@/entities/repository/ui/queries/repository-commits.constants";

vi.mock("@/entities/repository/domain/use-cases/get-repository-commits");

const getRepositoryCommitsMock = vi.mocked(getRepositoryCommits);

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

function buildUnavailableLog(reason: RepositoryGitUnavailableReason | null): RepositoryCommitLog {
  return {
    ...buildLog(RepositoryGitCondition.UNAVAILABLE, 0),
    unavailable: reason === null ? null : { reason, message: reason },
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
  const result = structuralSharing(oldData, newData) as typeof newData;
  return { newData, result };
}

describe("getRepositoryCommitsQueryOptions", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  test("keeps the loaded commits but records the unavailable answer when a refetch answers unavailable", () => {
    // GIVEN
    const loaded = [
      {
        ...buildLog(RepositoryGitCondition.BEHIND, REPOSITORY_COMMITS_PAGE_SIZE),
        fetched_at: "2026-01-01T00:00:00Z",
        checked_at: "2026-01-02T00:00:00Z",
        imported_commit: buildCommit(3).hash,
        remote_head: buildCommit(0).hash,
        pending_count: 3,
      },
      buildLog(RepositoryGitCondition.BEHIND, 2),
    ];
    const coldPage = buildLog(RepositoryGitCondition.UNAVAILABLE, 0);

    // WHEN
    const { result } = resolveStructuralSharing(loaded, [coldPage]);

    // THEN
    expect(result.pages).toEqual([
      {
        ...loaded[0],
        condition: RepositoryGitCondition.UNAVAILABLE,
        unavailable: coldPage.unavailable,
        pending_count: null,
      },
      loaded[1],
    ]);
  });

  test("still keeps the loaded commits when a second refetch answers unavailable", () => {
    // GIVEN
    const loaded = [buildLog(RepositoryGitCondition.IN_SYNC, 2)];
    const cold = [buildLog(RepositoryGitCondition.UNAVAILABLE, 0)];
    const { result: afterFirstCold } = resolveStructuralSharing(loaded, cold);

    // WHEN
    const { result } = resolveStructuralSharing(afterFirstCold.pages, cold);

    // THEN
    expect(result.pages[0]?.commits).toEqual(loaded[0]?.commits);
    expect(result.pages[0]?.condition).toBe(RepositoryGitCondition.UNAVAILABLE);
  });

  test("replaces the kept commits once a refetch answers with a git state again", () => {
    // GIVEN
    const loaded = [buildLog(RepositoryGitCondition.IN_SYNC, 2)];
    const cold = [buildLog(RepositoryGitCondition.UNAVAILABLE, 0)];
    const { result: afterCold } = resolveStructuralSharing(loaded, cold);
    const fresh = [buildLog(RepositoryGitCondition.BEHIND, 5)];

    // WHEN
    const { newData, result } = resolveStructuralSharing(afterCold.pages, fresh);

    // THEN
    expect(result).toEqual(newData);
  });

  test.each([
    {
      reason: RepositoryGitUnavailableReason.NOT_CLONED,
      interval: REPOSITORY_COMMITS_POLL_INTERVAL_MS,
    },
    { reason: RepositoryGitUnavailableReason.NOT_IMPLEMENTED, interval: false },
  ])("polls as for $reason after that answer arrives over loaded commits", ({
    reason,
    interval,
  }) => {
    // GIVEN
    const loaded = [buildLog(RepositoryGitCondition.IN_SYNC, 2)];
    const { result } = resolveStructuralSharing(loaded, [buildUnavailableLog(reason)]);

    // WHEN
    const nextInterval = resolveRefetchInterval(result.pages);

    // THEN
    expect(nextInterval).toBe(interval);
  });

  test("appends a page fetched after a refetch answered unavailable", () => {
    // GIVEN
    const loaded = buildLog(RepositoryGitCondition.BEHIND, REPOSITORY_COMMITS_PAGE_SIZE);
    const keptAfterColdPoll = { ...loaded, condition: RepositoryGitCondition.UNAVAILABLE };
    const nextPage = buildLog(RepositoryGitCondition.BEHIND, 3);

    // WHEN
    const { result } = resolveStructuralSharing([keptAfterColdPoll], [keptAfterColdPoll, nextPage]);

    // THEN
    expect(result.pages).toHaveLength(2);
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

  test.each([
    RepositoryGitUnavailableReason.NOT_CLONED,
    RepositoryGitUnavailableReason.TIMEOUT,
    null,
  ])("polls while the first page is unavailable with reason %s", (reason) => {
    // GIVEN
    const pages = [buildUnavailableLog(reason)];

    // WHEN
    const interval = resolveRefetchInterval(pages);

    // THEN
    expect(interval).toBe(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
  });

  test("does not poll when reading commits is not implemented", () => {
    // GIVEN
    const pages = [buildUnavailableLog(RepositoryGitUnavailableReason.NOT_IMPLEMENTED)];

    // WHEN
    const interval = resolveRefetchInterval(pages);

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
  ])("does not poll once the first page answers %s", (condition) => {
    // GIVEN
    const pages = [buildLog(condition)];

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

  test("stops paging when the last page answers unavailable", () => {
    // GIVEN
    const { getNextPageParam } = getRepositoryCommitsQueryOptions(PARAMS);
    const firstPage = buildLog(RepositoryGitCondition.IN_SYNC, REPOSITORY_COMMITS_PAGE_SIZE);
    const lastPage = buildLog(RepositoryGitCondition.UNAVAILABLE, 0);

    // WHEN
    const nextOffset = getNextPageParam(
      lastPage,
      [firstPage, lastPage],
      REPOSITORY_COMMITS_PAGE_SIZE,
      [0, REPOSITORY_COMMITS_PAGE_SIZE]
    );

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

  describe("feeding the commit status", () => {
    const statusKey = repositoriesQueryKeys.commitStatus(PARAMS);

    test("writes the status of the first page", async () => {
      // GIVEN
      const client = new QueryClient();
      getRepositoryCommitsMock.mockResolvedValue({
        ...buildLog(RepositoryGitCondition.BEHIND),
        pending_count: 4,
      });

      // WHEN
      await client.fetchInfiniteQuery(getRepositoryCommitsQueryOptions(PARAMS));

      // THEN
      expect(client.getQueryData(statusKey)).toEqual({
        condition: RepositoryGitCondition.BEHIND,
        pending_count: 4,
        unavailable: null,
      });
    });

    test("leaves the status alone for a later page", async () => {
      // GIVEN
      const client = new QueryClient();
      getRepositoryCommitsMock.mockResolvedValue(buildLog(RepositoryGitCondition.BEHIND));

      // WHEN
      await client.fetchInfiniteQuery({
        ...getRepositoryCommitsQueryOptions(PARAMS),
        initialPageParam: REPOSITORY_COMMITS_PAGE_SIZE,
      });

      // THEN
      expect(client.getQueryData(statusKey)).toBeUndefined();
    });

    test("keeps a known status when the first page answers unavailable", async () => {
      // GIVEN
      const client = new QueryClient();
      const known = {
        condition: RepositoryGitCondition.IN_SYNC,
        pending_count: null,
        unavailable: null,
      };
      client.setQueryData(statusKey, known);
      getRepositoryCommitsMock.mockResolvedValue(buildLog(RepositoryGitCondition.UNAVAILABLE, 0));

      // WHEN
      await client.fetchInfiniteQuery(getRepositoryCommitsQueryOptions(PARAMS));

      // THEN
      expect(client.getQueryData(statusKey)).toEqual(known);
    });
  });

  test("does not replay every loaded page on a quick remount", async () => {
    // GIVEN
    vi.useFakeTimers({ toFake: ["Date"] });
    const client = new QueryClient();
    getRepositoryCommitsMock.mockResolvedValue(buildLog(RepositoryGitCondition.IN_SYNC));
    await client.fetchInfiniteQuery(getRepositoryCommitsQueryOptions(PARAMS));

    // WHEN
    vi.advanceTimersByTime(REPOSITORY_COMMITS_STALE_TIME_MS - 1);
    await client.fetchInfiniteQuery(getRepositoryCommitsQueryOptions(PARAMS));

    // THEN
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1);
    await client.fetchInfiniteQuery(getRepositoryCommitsQueryOptions(PARAMS));
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(2);
  });
});
