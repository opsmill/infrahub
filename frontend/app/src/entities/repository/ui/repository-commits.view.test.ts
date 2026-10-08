import { describe, expect, test } from "vitest";

import {
  type RepositoryCommit,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import {
  canLoadOlderCommits,
  getCommitLogWithoutPages,
  getConditionNotice,
  getEmptyState,
  getFreshness,
  getLoadedCommits,
  getNextPageState,
  getNoCommitLogState,
  getStateBadges,
  isLoadingFirstPage,
  isShowingStaleCommits,
} from "@/entities/repository/ui/repository-commits.view";

const IMPORTED_HASH = "a".repeat(40);
const OTHER_HASH = "b".repeat(40);

function buildCommit(hash: string, summary = "Add device inventory"): RepositoryCommit {
  return {
    hash,
    short_hash: hash.slice(0, 7),
    summary,
    author_name: "Ada Lovelace",
    authored_at: "2025-03-10T10:00:00Z",
    state: RepositoryCommitState.HISTORY,
  };
}

describe("getLoadedCommits", () => {
  test("keeps page order and drops a commit repeated across a page boundary", () => {
    // GIVEN
    const pages = [
      { commits: [buildCommit(IMPORTED_HASH), buildCommit(OTHER_HASH)] },
      { commits: [buildCommit(OTHER_HASH), buildCommit("c".repeat(40))] },
    ];

    // WHEN
    const commits = getLoadedCommits(pages);

    // THEN
    expect(commits.map(({ hash }) => hash)).toEqual([IMPORTED_HASH, OTHER_HASH, "c".repeat(40)]);
  });
});

describe("getEmptyState", () => {
  test("uses the worker's message when the log is not available yet", () => {
    // WHEN
    const emptyState = getEmptyState(
      { reason: RepositoryGitUnavailableReason.NOT_CLONED, message: "Not cloned" },
      { isRetrying: true }
    );

    // THEN
    expect(emptyState).toEqual({ title: "Commit log not available yet", message: "Not cloned" });
  });

  test("keeps the worker's not-cloned message and asks for a refresh once retrying has stopped", () => {
    // WHEN
    const emptyState = getEmptyState(
      { reason: RepositoryGitUnavailableReason.NOT_CLONED, message: "Not cloned." },
      { isRetrying: false }
    );

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available yet",
      message: "Not cloned. Refresh to check again.",
    });
  });

  test("says no worker answered and asks for a refresh once retrying a timeout has stopped", () => {
    // WHEN
    const emptyState = getEmptyState(
      { reason: RepositoryGitUnavailableReason.TIMEOUT, message: "Timed out" },
      { isRetrying: false }
    );

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available yet",
      message: "No worker has answered yet. Refresh to check again.",
    });
  });

  test("says the log is not available, without a yet, when reading commits is not implemented", () => {
    // WHEN
    const emptyState = getEmptyState(
      {
        reason: RepositoryGitUnavailableReason.NOT_IMPLEMENTED,
        message: "Reading commits is not implemented",
      },
      { isRetrying: false }
    );

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available",
      message: "Reading commits is not implemented",
    });
  });

  test("falls back to a version message when not implemented carries an empty message", () => {
    // WHEN
    const emptyState = getEmptyState(
      { reason: RepositoryGitUnavailableReason.NOT_IMPLEMENTED, message: "" },
      { isRetrying: false }
    );

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available",
      message: "Reading commits is not available in this version of Infrahub.",
    });
  });

  test("still says not available yet when the read timed out", () => {
    // WHEN
    const emptyState = getEmptyState(
      { reason: RepositoryGitUnavailableReason.TIMEOUT, message: "Timed out" },
      { isRetrying: true }
    );

    // THEN
    expect(emptyState).toEqual({ title: "Commit log not available yet", message: "Timed out" });
  });

  test.each([
    { reason: RepositoryGitUnavailableReason.NOT_CLONED, message: "" },
    { reason: null, message: "" },
  ])("falls back to a waiting message when $reason carries an empty message", (unavailable) => {
    // WHEN
    const emptyState = getEmptyState(unavailable, { isRetrying: true });

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available yet",
      message: "Waiting for a worker to answer.",
    });
  });
});

describe("getNoCommitLogState", () => {
  test.each([
    { condition: RepositoryGitCondition.NOT_TRACKED, message: "This branch tracks no remote ref." },
    {
      condition: RepositoryGitCondition.NO_REMOTE,
      message: "The tracked ref has no remote counterpart.",
    },
  ])("explains why $condition has no commit log", ({ condition, message }) => {
    // WHEN
    const emptyState = getNoCommitLogState({ condition });

    // THEN
    expect(emptyState).toEqual({ title: "No commit log", message });
  });

  test.each([
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.BEHIND,
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
  ])("leaves %s to the table's own empty row", (condition) => {
    // WHEN
    const emptyState = getNoCommitLogState({ condition });

    // THEN
    expect(emptyState).toBeNull();
  });
});

describe("getStateBadges", () => {
  test("marks the remote head that is also the imported commit with both labels", () => {
    // GIVEN
    const commit = { hash: IMPORTED_HASH, state: RepositoryCommitState.HEAD };

    // WHEN
    const badges = getStateBadges(commit, IMPORTED_HASH);

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(["Remote head", "Imported"]);
  });

  test("marks a remote head ahead of the imported commit as the head only", () => {
    // GIVEN
    const commit = { hash: OTHER_HASH, state: RepositoryCommitState.HEAD };

    // WHEN
    const badges = getStateBadges(commit, IMPORTED_HASH);

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(["Remote head"]);
  });

  test.each([
    { state: RepositoryCommitState.IMPORTED, labels: ["Imported"] },
    { state: RepositoryCommitState.PENDING, labels: ["Pending import"] },
    { state: RepositoryCommitState.UNRELATED, labels: ["Not on current history"] },
    { state: RepositoryCommitState.HISTORY, labels: [] },
  ])("labels a $state commit from its state", ({ state, labels }) => {
    // WHEN
    const badges = getStateBadges({ hash: OTHER_HASH, state }, IMPORTED_HASH);

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(labels);
  });

  test("shows no badge for a state this client does not know", () => {
    // GIVEN
    const commit = { hash: "a".repeat(40), state: "FUTURE_STATE" };

    // WHEN
    // @ts-expect-error A newer server can send a state this client's generated enum does not list.
    const badges = getStateBadges(commit, null);

    // THEN
    expect(badges).toEqual([]);
  });
});

describe("getFreshness", () => {
  test("shows both times when the last check did not bring the update", () => {
    // GIVEN
    const log = {
      git_ref: "v1.2.0",
      checked_at: "2025-03-11T08:30:00Z",
      fetched_at: "2025-03-10T12:00:00Z",
    };

    // WHEN
    const freshness = getFreshness(log);

    // THEN
    expect(freshness).toEqual({
      trackedRef: "v1.2.0",
      checkedAt: "2025-03-11T08:30:00Z",
      updatedAt: "2025-03-10T12:00:00Z",
    });
  });

  test("hides the update time when the last check brought it", () => {
    // GIVEN
    const log = {
      git_ref: "main",
      checked_at: "2025-03-11T08:30:00Z",
      fetched_at: "2025-03-11T08:30:00Z",
    };

    // WHEN
    const freshness = getFreshness(log);

    // THEN
    expect(freshness.checkedAt).toBe("2025-03-11T08:30:00Z");
    expect(freshness.updatedAt).toBeNull();
  });

  test("shows only the update time when the remote was never checked", () => {
    // GIVEN
    const log = { git_ref: "main", checked_at: null, fetched_at: "2025-03-10T12:00:00Z" };

    // WHEN
    const freshness = getFreshness(log);

    // THEN
    expect(freshness.checkedAt).toBeNull();
    expect(freshness.updatedAt).toBe("2025-03-10T12:00:00Z");
  });

  test("shows no time and no ref when nothing was fetched or tracked", () => {
    // GIVEN
    const log = { git_ref: null, checked_at: null, fetched_at: null };

    // WHEN
    const freshness = getFreshness(log);

    // THEN
    expect(freshness).toEqual({ trackedRef: null, checkedAt: null, updatedAt: null });
  });
});

describe("getConditionNotice", () => {
  test("warns that a rewritten ref reports nothing as pending", () => {
    // WHEN
    const notice = getConditionNotice({
      condition: RepositoryGitCondition.REWRITTEN,
      pending_count: null,
    });

    // THEN
    expect(notice?.tone).toBe("warning");
    expect(notice?.message).toMatch(/^The tracked ref was rewritten\./);
  });

  test("warns that the imported commit is missing from the remote", () => {
    // WHEN
    const notice = getConditionNotice({
      condition: RepositoryGitCondition.ORPHANED,
      pending_count: null,
    });

    // THEN
    expect(notice).toEqual({
      tone: "warning",
      message: "The imported commit could not be found on the remote.",
    });
  });

  test("counts the commits pending import when behind", () => {
    // WHEN
    const notice = getConditionNotice({
      condition: RepositoryGitCondition.BEHIND,
      pending_count: 2,
    });

    // THEN
    expect(notice).toEqual({ tone: "neutral", message: "2 commits pending import" });
  });

  test("says nothing when behind without a count", () => {
    // WHEN
    const notice = getConditionNotice({
      condition: RepositoryGitCondition.BEHIND,
      pending_count: null,
    });

    // THEN
    expect(notice).toBeNull();
  });

  test.each([
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.NOT_TRACKED,
    RepositoryGitCondition.UNAVAILABLE,
  ])("says nothing for %s", (condition) => {
    // WHEN
    const notice = getConditionNotice({ condition, pending_count: null });

    // THEN
    expect(notice).toBeNull();
  });
});

function buildUnavailableError(reason: RepositoryGitUnavailableReason) {
  return new RepositoryGitUnavailableError({
    repository_id: "repo-1",
    branch_name: "main",
    git_ref: "main",
    condition: RepositoryGitCondition.UNAVAILABLE,
    imported_commit: null,
    remote_head: null,
    pending_count: null,
    fetched_at: null,
    checked_at: null,
    unavailable: { reason, message: reason },
    commits: [],
  });
}

describe("getCommitLogWithoutPages", () => {
  test("reports an unavailable answer that is still being retried", () => {
    // GIVEN
    const failureReason = buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED);

    // WHEN
    const state = getCommitLogWithoutPages({ error: null, failureReason, isFetching: true });

    // THEN
    expect(state).toEqual({ kind: "unavailable", error: failureReason, isRetrying: true });
  });

  test("reports an unavailable answer that is no longer retried", () => {
    // GIVEN
    const error = buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED);

    // WHEN
    const state = getCommitLogWithoutPages({ error, failureReason: error, isFetching: false });

    // THEN
    expect(state).toEqual({ kind: "unavailable", error, isRetrying: false });
  });

  test("reports an unavailable answer as retried again while a refresh after the last retry runs", () => {
    // GIVEN
    const error = buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED);

    // WHEN
    const state = getCommitLogWithoutPages({ error, failureReason: null, isFetching: true });

    // THEN
    expect(state).toEqual({ kind: "unavailable", error, isRetrying: true });
  });

  test("reports any other error as a failed read", () => {
    // GIVEN
    const error = new Error("Permission denied");

    // WHEN
    const state = getCommitLogWithoutPages({ error, failureReason: error, isFetching: false });

    // THEN
    expect(state).toEqual({ kind: "failed", error });
  });

  test("reports a first load that has not failed yet as loading", () => {
    // WHEN
    const state = getCommitLogWithoutPages({
      error: null,
      failureReason: null,
      isFetching: true,
    });

    // THEN
    expect(state).toEqual({ kind: "loading" });
  });
});

describe("isLoadingFirstPage", () => {
  test.each([
    {
      name: "the first attempt is in flight",
      isPending: true,
      failureReason: null,
      expected: true,
    },
    {
      name: "an unavailable answer is being retried",
      isPending: true,
      failureReason: buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED),
      expected: false,
    },
    { name: "the log has loaded", isPending: false, failureReason: null, expected: false },
  ])("is $expected when $name", ({ isPending, failureReason, expected }) => {
    // WHEN
    const isLoading = isLoadingFirstPage({ isPending, failureReason });

    // THEN
    expect(isLoading).toBe(expected);
  });
});

describe("isShowingStaleCommits", () => {
  const failureReason = buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED);

  test.each([
    {
      name: "a refetch failed",
      isRefetchError: true,
      isRefetching: false,
      failureReason,
      expected: true,
    },
    {
      name: "a refetch is being retried",
      isRefetchError: false,
      isRefetching: true,
      failureReason,
      expected: true,
    },
    {
      name: "a refresh runs after an older page failed",
      isRefetchError: true,
      isRefetching: true,
      failureReason: null,
      expected: false,
    },
    {
      name: "a refetch has not failed yet",
      isRefetchError: false,
      isRefetching: true,
      failureReason: null,
      expected: false,
    },
    {
      name: "only a later page failed",
      isRefetchError: false,
      isRefetching: false,
      failureReason,
      expected: false,
    },
  ])("is $expected when $name", ({ isRefetchError, isRefetching, failureReason, expected }) => {
    // WHEN
    const isStale = isShowingStaleCommits({ isRefetchError, isRefetching, failureReason });

    // THEN
    expect(isStale).toBe(expected);
  });
});

describe("canLoadOlderCommits", () => {
  test.each([
    { hasNextPage: true, isRefetching: false, isRefetchError: false, expected: true },
    { hasNextPage: false, isRefetching: false, isRefetchError: false, expected: false },
    { hasNextPage: true, isRefetching: true, isRefetchError: false, expected: false },
    { hasNextPage: true, isRefetching: false, isRefetchError: true, expected: false },
  ])(
    "returns $expected with a next page $hasNextPage, refreshing $isRefetching, failed refresh $isRefetchError",
    ({ expected, ...state }) => {
      // WHEN
      const canLoad = canLoadOlderCommits(state);

      // THEN
      expect(canLoad).toBe(expected);
    }
  );
});

describe("getNextPageState", () => {
  const failureReason = buildUnavailableError(RepositoryGitUnavailableReason.NOT_CLONED);

  test.each([
    {
      name: "no page is loading",
      isFetchNextPageError: false,
      isFetchingNextPage: false,
      failureReason: null,
      expected: "idle",
    },
    {
      name: "a page is loading for the first time",
      isFetchNextPageError: false,
      isFetchingNextPage: true,
      failureReason: null,
      expected: "loading",
    },
    {
      name: "a page is being retried after an unavailable answer",
      isFetchNextPageError: false,
      isFetchingNextPage: true,
      failureReason,
      expected: "retry-pending",
    },
    {
      name: "a page failed",
      isFetchNextPageError: true,
      isFetchingNextPage: false,
      failureReason,
      expected: "failed",
    },
    {
      name: "a failed page is being retried after an unavailable answer",
      isFetchNextPageError: true,
      isFetchingNextPage: true,
      failureReason,
      expected: "retry-pending",
    },
    {
      name: "a page loads after a refresh failed, before any page failed",
      isFetchNextPageError: true,
      isFetchingNextPage: true,
      failureReason: null,
      expected: "loading",
    },
  ])("is $expected when $name", ({ expected, ...state }) => {
    // WHEN
    const nextPageState = getNextPageState(state);

    // THEN
    expect(nextPageState).toBe(expected);
  });
});
