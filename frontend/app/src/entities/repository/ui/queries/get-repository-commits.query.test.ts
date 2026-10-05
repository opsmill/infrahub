import { focusManager, InfiniteQueryObserver, QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  type RepositoryCommit,
  type RepositoryCommitLog,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import { getRepositoryCommits } from "@/entities/repository/domain/use-cases/get-repository-commits";
import { getRepositoryCommitsQueryOptions } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  REPOSITORY_COMMITS_PAGE_SIZE,
  REPOSITORY_COMMITS_POLL_INTERVAL_MS,
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
    unavailable: null,
    commits: Array.from({ length: commitCount }, (_, index) => buildCommit(index)),
  };
}

function buildUnavailableError(reason: RepositoryGitUnavailableReason | null) {
  return new RepositoryGitUnavailableError({
    ...buildLog(RepositoryGitCondition.UNAVAILABLE, 0),
    unavailable: reason === null ? null : { reason, message: reason },
  });
}

function resolveRefetchInterval(error: Error | null) {
  const { refetchInterval } = getRepositoryCommitsQueryOptions(PARAMS);
  if (typeof refetchInterval !== "function") {
    throw new Error("refetchInterval is expected to be a function");
  }
  return refetchInterval({ state: { error } } as Parameters<typeof refetchInterval>[0]);
}

function observeCommits() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const observer = new InfiniteQueryObserver(client, getRepositoryCommitsQueryOptions(PARAMS));
  const unsubscribe = observer.subscribe(() => {});
  return { observer, unsubscribe };
}

describe("getRepositoryCommitsQueryOptions", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.resetAllMocks();
    focusManager.setFocused(undefined);
  });

  test.each([
    RepositoryGitUnavailableReason.NOT_CLONED,
    RepositoryGitUnavailableReason.TIMEOUT,
    null,
  ])("polls while the commit log is unavailable with reason %s", (reason) => {
    // GIVEN
    const error = buildUnavailableError(reason);

    // WHEN
    const interval = resolveRefetchInterval(error);

    // THEN
    expect(interval).toBe(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
  });

  test("does not poll when reading commits is not implemented", () => {
    // GIVEN
    const error = buildUnavailableError(RepositoryGitUnavailableReason.NOT_IMPLEMENTED);

    // WHEN
    const interval = resolveRefetchInterval(error);

    // THEN
    expect(interval).toBe(false);
  });

  test("does not poll after an error that is not an unavailable answer", () => {
    // GIVEN
    const error = new Error("Permission denied");

    // WHEN
    const interval = resolveRefetchInterval(error);

    // THEN
    expect(interval).toBe(false);
  });

  test("does not poll without an error", () => {
    // WHEN
    const interval = resolveRefetchInterval(null);

    // THEN
    expect(interval).toBe(false);
  });

  test("keeps polling a query in error until a worker answers, then stops", async () => {
    // GIVEN
    vi.useFakeTimers();
    focusManager.setFocused(true);
    getRepositoryCommitsMock
      .mockRejectedValueOnce(buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED))
      .mockRejectedValueOnce(buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED))
      .mockResolvedValue(buildLog(RepositoryGitCondition.IN_SYNC));

    // WHEN
    const { observer, unsubscribe } = observeCommits();
    await vi.advanceTimersByTimeAsync(0);

    // THEN
    expect(observer.getCurrentResult().error).toBeInstanceOf(RepositoryGitUnavailableError);
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
    expect(observer.getCurrentResult().error).toBeInstanceOf(RepositoryGitUnavailableError);
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_POLL_INTERVAL_MS);
    expect(observer.getCurrentResult().status).toBe("success");
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(3);
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_POLL_INTERVAL_MS * 3);
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(3);
    unsubscribe();
  });

  test.each([
    {
      name: "reading commits is not implemented",
      error: buildUnavailableError(RepositoryGitUnavailableReason.NOT_IMPLEMENTED),
    },
    { name: "the read fails", error: new Error("Permission denied") },
  ])("does not poll a query in error when $name", async ({ error }) => {
    // GIVEN
    vi.useFakeTimers();
    focusManager.setFocused(true);
    getRepositoryCommitsMock.mockRejectedValue(error);

    // WHEN
    const { observer, unsubscribe } = observeCommits();
    await vi.advanceTimersByTimeAsync(REPOSITORY_COMMITS_POLL_INTERVAL_MS * 3);

    // THEN
    expect(observer.getCurrentResult().error).toBe(error);
    expect(getRepositoryCommitsMock).toHaveBeenCalledTimes(1);
    unsubscribe();
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
      params,
      "commits",
      { limit: REPOSITORY_COMMITS_PAGE_SIZE },
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
