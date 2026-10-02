import { describe, expect, test } from "vitest";

import {
  type RepositoryCommit,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import {
  getConditionNotice,
  getEmptyState,
  getFreshness,
  getHistoryRetry,
  getLoadedCommits,
  getStateBadges,
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
  test("uses the worker's message when the log is unavailable", () => {
    // GIVEN
    const log = {
      condition: RepositoryGitCondition.UNAVAILABLE,
      unavailable: { reason: RepositoryGitUnavailableReason.NOT_CLONED, message: "Not cloned" },
    };

    // WHEN
    const emptyState = getEmptyState(log);

    // THEN
    expect(emptyState).toEqual({ title: "Commit log not available yet", message: "Not cloned" });
  });

  test("says the log is not available, without a yet, when reading commits is not implemented", () => {
    // GIVEN
    const log = {
      condition: RepositoryGitCondition.UNAVAILABLE,
      unavailable: {
        reason: RepositoryGitUnavailableReason.NOT_IMPLEMENTED,
        message: "Reading commits is not implemented",
      },
    };

    // WHEN
    const emptyState = getEmptyState(log);

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available",
      message: "Reading commits is not implemented",
    });
  });

  test("falls back to a version message when not implemented carries an empty message", () => {
    // GIVEN
    const log = {
      condition: RepositoryGitCondition.UNAVAILABLE,
      unavailable: { reason: RepositoryGitUnavailableReason.NOT_IMPLEMENTED, message: "" },
    };

    // WHEN
    const emptyState = getEmptyState(log);

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available",
      message: "Reading commits is not available in this version of Infrahub.",
    });
  });

  test("still says not available yet when the read timed out", () => {
    // GIVEN
    const log = {
      condition: RepositoryGitCondition.UNAVAILABLE,
      unavailable: { reason: RepositoryGitUnavailableReason.TIMEOUT, message: "Timed out" },
    };

    // WHEN
    const emptyState = getEmptyState(log);

    // THEN
    expect(emptyState).toEqual({ title: "Commit log not available yet", message: "Timed out" });
  });

  test("falls back to a waiting message when the unavailable log has no reason", () => {
    // GIVEN
    const log = { condition: RepositoryGitCondition.UNAVAILABLE, unavailable: null };

    // WHEN
    const emptyState = getEmptyState(log);

    // THEN
    expect(emptyState?.message).toBe("Waiting for a worker to answer.");
  });

  test.each([
    { condition: RepositoryGitCondition.NOT_TRACKED, message: "This branch tracks no remote ref." },
    {
      condition: RepositoryGitCondition.NO_REMOTE,
      message: "The tracked ref has no remote counterpart.",
    },
  ])("explains why $condition has no commit log", ({ condition, message }) => {
    // WHEN
    const emptyState = getEmptyState({ condition, unavailable: null });

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
    const emptyState = getEmptyState({ condition, unavailable: null });

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
    const commit = { hash: "a".repeat(40), state: "FUTURE_STATE" as RepositoryCommitState };

    // WHEN
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

describe("getHistoryRetry", () => {
  const available = { condition: RepositoryGitCondition.IN_SYNC };
  const cold = { condition: RepositoryGitCondition.UNAVAILABLE };

  test("offers no retry for a single unavailable first page", () => {
    // GIVEN
    const pages = [cold];

    // WHEN
    const retry = getHistoryRetry(pages, { isFetchNextPageError: false });

    // THEN
    expect(retry).toBeNull();
  });

  test("refetches when a later page answers unavailable", () => {
    // GIVEN
    const pages = [available, cold];

    // WHEN
    const retry = getHistoryRetry(pages, { isFetchNextPageError: false });

    // THEN
    expect(retry).toBe("refetch");
  });

  test("fetches the next page again when fetching it failed", () => {
    // GIVEN
    const pages = [available, available];

    // WHEN
    const retry = getHistoryRetry(pages, { isFetchNextPageError: true });

    // THEN
    expect(retry).toBe("fetch-next-page");
  });

  test("prefers fetching the next page when it failed after an unavailable page", () => {
    // GIVEN
    const pages = [available, cold];

    // WHEN
    const retry = getHistoryRetry(pages, { isFetchNextPageError: true });

    // THEN
    expect(retry).toBe("fetch-next-page");
  });

  test("offers no retry when every loaded page is available", () => {
    // GIVEN
    const pages = [available, available];

    // WHEN
    const retry = getHistoryRetry(pages, { isFetchNextPageError: false });

    // THEN
    expect(retry).toBeNull();
  });
});

describe("isShowingStaleCommits", () => {
  test("flags loaded commits kept over a failed refresh", () => {
    // WHEN
    const result = isShowingStaleCommits({
      firstPage: { condition: RepositoryGitCondition.IN_SYNC },
      hasError: true,
      isFetchNextPageError: false,
      loadedCommitCount: 3,
    });

    // THEN
    expect(result).toBe(true);
  });

  test("leaves a failed next page to the history retry", () => {
    // WHEN
    const result = isShowingStaleCommits({
      firstPage: { condition: RepositoryGitCondition.IN_SYNC },
      hasError: true,
      isFetchNextPageError: true,
      loadedCommitCount: 3,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("does not flag a failure with nothing loaded", () => {
    // WHEN
    const result = isShowingStaleCommits({
      firstPage: { condition: RepositoryGitCondition.IN_SYNC },
      hasError: true,
      isFetchNextPageError: false,
      loadedCommitCount: 0,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("does not flag loaded commits without an error", () => {
    // WHEN
    const result = isShowingStaleCommits({
      firstPage: { condition: RepositoryGitCondition.IN_SYNC },
      hasError: false,
      isFetchNextPageError: false,
      loadedCommitCount: 3,
    });

    // THEN
    expect(result).toBe(false);
  });

  test("flags loaded commits kept over an unavailable first page", () => {
    // WHEN
    const result = isShowingStaleCommits({
      firstPage: { condition: RepositoryGitCondition.UNAVAILABLE },
      hasError: false,
      isFetchNextPageError: false,
      loadedCommitCount: 3,
    });

    // THEN
    expect(result).toBe(true);
  });

  test("does not flag an unavailable first page with nothing loaded", () => {
    // WHEN
    const result = isShowingStaleCommits({
      firstPage: { condition: RepositoryGitCondition.UNAVAILABLE },
      hasError: false,
      isFetchNextPageError: false,
      loadedCommitCount: 0,
    });

    // THEN
    expect(result).toBe(false);
  });
});
