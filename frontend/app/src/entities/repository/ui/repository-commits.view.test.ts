import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { describe, expect, test } from "vitest";

import { ERROR_CODES } from "@/shared/api/errors";
import { BranchStatus } from "@/shared/api/graphql/generated/types";

import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import {
  type RepositoryCommit,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import {
  type ActionAccess,
  BRANCH_MERGE_FAILED,
  BRANCH_MERGED,
  BRANCH_MERGING,
  BRANCH_NEEDS_REBASE,
  type CommitLogStatusContext,
  type CommitLogTextPart,
  canLoadOlderCommits,
  DEFAULT_BRANCH_EDIT_DENIED,
  formatCommitsTabCount,
  getBranchStatusDeniedReason,
  getCheckAction,
  getCommitLogHeaderState,
  getCommitLogStatus,
  getCommitLogWithoutPages,
  getCommitsTabBadge,
  getDeniedReasons,
  getEmptyState,
  getFreshness,
  getLoadedCommits,
  getNextPageState,
  getReasonId,
  getRebaseAccess,
  getRepositoryActionAccess,
  getStateBadges,
  getUnavailableStatus,
  isErrorWithoutClientToast,
  isLoadingFirstPage,
  isShowingStaleCommits,
  mayKeepOwnCommit,
  NO_WORKER_ANSWER,
  REBASE_DEFAULT_BRANCH,
  REBASE_PERMISSION_DENIED,
  REBASE_SIGN_IN_REQUIRED,
  REPOSITORY_SIGN_IN_REQUIRED,
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
      message: "Not cloned. Use the refresh button to check again.",
    });
  });

  test("says no worker answered and asks for a refresh once retrying an answer without a reason has stopped", () => {
    // WHEN
    const emptyState = getEmptyState({ reason: null, message: "No answer" }, { isRetrying: false });

    // THEN
    expect(emptyState).toEqual({
      title: "Commit log not available yet",
      message: "No worker has answered yet. Use the refresh button to check again.",
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

  test("still says not available yet when the answer carries no reason", () => {
    // WHEN
    const emptyState = getEmptyState({ reason: null, message: "No answer" }, { isRetrying: true });

    // THEN
    expect(emptyState).toEqual({ title: "Commit log not available yet", message: "No answer" });
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

describe("getStateBadges", () => {
  test("marks the remote head that is also the imported commit with both labels", () => {
    // GIVEN
    const commit = { hash: IMPORTED_HASH, state: RepositoryCommitState.HEAD };

    // WHEN
    const badges = getStateBadges(commit, {
      importedCommit: IMPORTED_HASH,
      condition: RepositoryGitCondition.BEHIND,
      rebaseOnly: false,
    });

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(["Remote head", "Imported"]);
  });

  test("marks a remote head ahead of the imported commit as the head only", () => {
    // GIVEN
    const commit = { hash: OTHER_HASH, state: RepositoryCommitState.HEAD };

    // WHEN
    const badges = getStateBadges(commit, {
      importedCommit: IMPORTED_HASH,
      condition: RepositoryGitCondition.BEHIND,
      rebaseOnly: false,
    });

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(["Remote head"]);
  });

  test.each([
    { state: RepositoryCommitState.IMPORTED, labels: ["Imported"] },
    { state: RepositoryCommitState.PENDING, labels: ["Pending import"] },
    { state: RepositoryCommitState.UNRELATED, labels: ["Not on current history"] },
    { state: RepositoryCommitState.HISTORY, labels: [] },
    { state: RepositoryCommitState.NOT_ON_BRANCH, labels: ["Behind"] },
  ])("labels a $state commit from its state", ({ state, labels }) => {
    // WHEN
    const badges = getStateBadges(
      { hash: OTHER_HASH, state },
      {
        importedCommit: IMPORTED_HASH,
        condition: RepositoryGitCondition.BEHIND,
        rebaseOnly: false,
      }
    );

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(labels);
  });

  test("marks a remote head ahead of the branch's commit as behind", () => {
    // GIVEN
    const commit = { hash: OTHER_HASH, state: RepositoryCommitState.HEAD };

    // WHEN
    const badges = getStateBadges(commit, {
      importedCommit: IMPORTED_HASH,
      condition: RepositoryGitCondition.BEHIND,
      rebaseOnly: true,
    });

    // THEN
    expect(badges.map(({ label }) => label)).toEqual(["Remote head", "Behind"]);
  });

  test.each([RepositoryGitCondition.REWRITTEN, RepositoryGitCondition.ORPHANED])(
    "marks the remote head as the head only when a rebase-only branch is %s",
    (condition) => {
      // GIVEN
      const commit = { hash: OTHER_HASH, state: RepositoryCommitState.HEAD };

      // WHEN
      const badges = getStateBadges(commit, {
        importedCommit: IMPORTED_HASH,
        condition,
        rebaseOnly: true,
      });

      // THEN
      expect(badges.map(({ label }) => label)).toEqual(["Remote head"]);
    }
  );

  test("shows no badge for a state this client does not know", () => {
    // GIVEN
    const commit = { hash: "a".repeat(40), state: "FUTURE_STATE" };

    // WHEN
    // @ts-expect-error A newer server can send a state this client's generated enum does not list.
    const badges = getStateBadges(commit, {
      importedCommit: null,
      condition: RepositoryGitCondition.IN_SYNC,
      rebaseOnly: false,
    });

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

describe("formatCommitsTabCount", () => {
  test.each([
    { count: 3, expected: "3" },
    { count: 999, expected: "999" },
    { count: 1000, expected: "999+" },
    { count: 1284, expected: "999+" },
  ])("shows $count as $expected", ({ count, expected }) => {
    // WHEN
    const text = formatCommitsTabCount(count);

    // THEN
    expect(text).toBe(expected);
  });
});

describe("getCommitsTabBadge", () => {
  const SYNCED = { rebaseOnly: false, isReadOnly: false };
  const behind = (pending_count: number | null) => ({
    condition: RepositoryGitCondition.BEHIND,
    git_ref: "main",
    pending_count,
  });

  test("says the next sync imports the pending commits of a read-write repository", () => {
    // WHEN
    const badge = getCommitsTabBadge(behind(3), SYNCED);

    // THEN
    expect(badge).toEqual({
      kind: "pending-import",
      count: 3,
      summary: "3 commits pending import",
      tooltip: "3 commits pending import — the next sync imports them",
    });
  });

  test("asks for Import latest commit on a read-only repository", () => {
    // WHEN
    const badge = getCommitsTabBadge(behind(2), { ...SYNCED, isReadOnly: true });

    // THEN
    expect(badge).toMatchObject({
      kind: "pending-import",
      tooltip: "2 commits pending import — run Import latest commit to use them",
    });
  });

  test("counts the commits behind the tracked ref and asks for a rebase", () => {
    // WHEN
    const badge = getCommitsTabBadge(
      { ...behind(1), git_ref: "release-1.4" },
      { ...SYNCED, rebaseOnly: true }
    );

    // THEN
    expect(badge).toEqual({
      kind: "behind",
      count: 1,
      summary: "1 commit behind release-1.4",
      tooltip:
        "1 commit behind release-1.4 — a rebase moves the branch to the commit used on the default branch",
    });
  });

  test("keeps the exact number of a large count", () => {
    // WHEN
    const badge = getCommitsTabBadge(behind(1284), SYNCED);

    // THEN
    expect(badge).toMatchObject({ count: 1284, summary: "1,284 commits pending import" });
  });

  test("says the branch has diverged when the tracked ref was rewritten under a rebase-only branch", () => {
    // WHEN
    const badge = getCommitsTabBadge(
      { condition: RepositoryGitCondition.REWRITTEN, git_ref: "main", pending_count: null },
      { ...SYNCED, rebaseOnly: true }
    );

    // THEN
    expect(badge).toEqual({
      kind: "warning",
      summary: "diverged from main",
      tooltip:
        "This branch has diverged from main. A rebase moves the branch to the commit used on the default branch.",
    });
  });

  test.each([
    {
      condition: RepositoryGitCondition.REWRITTEN,
      summary: "history rewritten",
      tooltip: "The tracked ref was rewritten, so nothing is reported as pending import.",
    },
    {
      condition: RepositoryGitCondition.ORPHANED,
      summary: "imported commit missing",
      tooltip: "The imported commit could not be found on the remote.",
    },
    {
      condition: RepositoryGitCondition.REF_MISSING,
      summary: "tracked ref missing",
      tooltip:
        "The tracked branch or tag no longer exists on the remote. The imported commit is still in use.",
    },
  ])("warns without a count for $condition", ({ condition, summary, tooltip }) => {
    // WHEN
    const badge = getCommitsTabBadge({ condition, git_ref: "main", pending_count: null }, SYNCED);

    // THEN
    expect(badge).toEqual({ kind: "warning", summary, tooltip });
  });

  test.each([
    { case: "nothing pending", log: { ...behind(0) } },
    { case: "a BEHIND log without a count", log: behind(null) },
    {
      case: "IN_SYNC",
      log: { condition: RepositoryGitCondition.IN_SYNC, git_ref: "main", pending_count: null },
    },
    {
      case: "NOT_TRACKED",
      log: { condition: RepositoryGitCondition.NOT_TRACKED, git_ref: null, pending_count: null },
    },
    {
      case: "NO_REMOTE",
      log: { condition: RepositoryGitCondition.NO_REMOTE, git_ref: "main", pending_count: null },
    },
  ])("shows nothing for $case", ({ log }) => {
    // WHEN
    const badge = getCommitsTabBadge(log, SYNCED);

    // THEN
    expect(badge).toBeNull();
  });
});

describe("getRepositoryActionAccess", () => {
  const ALLOWED: PermissionDecision = { isAllowed: true };
  const DENIED: PermissionDecision = { isAllowed: false, message: "Ask an administrator." };

  test.each<{
    case: string;
    params: Parameters<typeof getRepositoryActionAccess>[0];
    expected: ActionAccess;
  }>([
    {
      case: "allows an update on another branch without the default branch permission",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: ALLOWED,
        isDefaultBranch: false,
        canEditDefaultBranch: false,
      },
      expected: { status: "allowed" },
    },
    {
      case: "keeps the reason of the update permission decision",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: DENIED,
        isDefaultBranch: false,
        canEditDefaultBranch: true,
      },
      expected: { status: "denied", reason: "Ask an administrator." },
    },
    {
      case: "names the update permission first on the default branch",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: DENIED,
        isDefaultBranch: true,
        canEditDefaultBranch: false,
      },
      expected: { status: "denied", reason: "Ask an administrator." },
    },
    {
      case: "names the default branch permission when the update is allowed",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: ALLOWED,
        isDefaultBranch: true,
        canEditDefaultBranch: false,
      },
      expected: { status: "denied", reason: DEFAULT_BRANCH_EDIT_DENIED },
    },
    {
      case: "waits without a reason while the default branch permission loads",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: ALLOWED,
        isDefaultBranch: true,
        canEditDefaultBranch: undefined,
      },
      expected: { status: "pending" },
    },
    {
      case: "keeps a known update denial while the default branch permission loads",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: DENIED,
        isDefaultBranch: true,
        canEditDefaultBranch: undefined,
      },
      expected: { status: "denied", reason: "Ask an administrator." },
    },
    {
      case: "asks a signed-out user to sign in before naming the default branch permission",
      params: {
        isAuthenticated: false,
        branchStatus: BranchStatus.OPEN,
        updatePermission: DENIED,
        isDefaultBranch: true,
        canEditDefaultBranch: false,
      },
      expected: { status: "denied", reason: REPOSITORY_SIGN_IN_REQUIRED },
    },
    {
      case: "asks a signed-out user to sign in before naming the branch status",
      params: {
        isAuthenticated: false,
        branchStatus: BranchStatus.NEED_REBASE,
        updatePermission: DENIED,
        isDefaultBranch: false,
        canEditDefaultBranch: undefined,
      },
      expected: { status: "denied", reason: REPOSITORY_SIGN_IN_REQUIRED },
    },
    {
      case: "names the branch status before the update permission",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.NEED_REBASE,
        updatePermission: DENIED,
        isDefaultBranch: false,
        canEditDefaultBranch: undefined,
      },
      expected: { status: "denied", reason: BRANCH_NEEDS_REBASE },
    },
    {
      case: "refuses a merged branch",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.MERGED,
        updatePermission: ALLOWED,
        isDefaultBranch: false,
        canEditDefaultBranch: undefined,
      },
      expected: { status: "denied", reason: BRANCH_MERGED },
    },
    {
      case: "allows an update on the default branch with both permissions",
      params: {
        isAuthenticated: true,
        branchStatus: BranchStatus.OPEN,
        updatePermission: ALLOWED,
        isDefaultBranch: true,
        canEditDefaultBranch: true,
      },
      expected: { status: "allowed" },
    },
  ])("$case", ({ params, expected }) => {
    expect(getRepositoryActionAccess(params)).toEqual(expected);
  });
});

describe("getBranchStatusDeniedReason", () => {
  test.each<[BranchStatus, string | null, string | null]>([
    [BranchStatus.OPEN, null, null],
    [BranchStatus.NEED_REBASE, BRANCH_NEEDS_REBASE, null],
    [BranchStatus.MERGING, BRANCH_MERGING, BRANCH_MERGING],
    [BranchStatus.MERGE_FAILED, BRANCH_MERGE_FAILED, BRANCH_MERGE_FAILED],
    [BranchStatus.MERGED, BRANCH_MERGED, BRANCH_MERGED],
  ])(
    "on a %s branch, denies a repository change with %j and a rebase with %j",
    (branchStatus, repositoryReason, rebaseReason) => {
      expect(getBranchStatusDeniedReason(branchStatus, "repository")).toBe(repositoryReason);
      expect(getBranchStatusDeniedReason(branchStatus, "rebase")).toBe(rebaseReason);
    }
  );
});

describe("getRebaseAccess", () => {
  const ALLOWED_PARAMS: Parameters<typeof getRebaseAccess>[0] = {
    isAuthenticated: true,
    isDefaultBranch: false,
    branchStatus: BranchStatus.OPEN,
    canRebase: true,
    isRunningKnown: true,
  };

  test.each<[string, Partial<Parameters<typeof getRebaseAccess>[0]>, ActionAccess]>([
    ["allows a signed-in user with the permission", {}, { status: "allowed" }],
    [
      "asks to sign in before checking anything else",
      {
        isAuthenticated: false,
        isDefaultBranch: true,
        branchStatus: BranchStatus.MERGED,
        canRebase: false,
      },
      { status: "denied", reason: REBASE_SIGN_IN_REQUIRED },
    ],
    [
      "refuses the default branch",
      { isDefaultBranch: true },
      { status: "denied", reason: REBASE_DEFAULT_BRANCH },
    ],
    [
      "names a merged branch before the missing permission",
      { branchStatus: BranchStatus.MERGED, canRebase: false },
      { status: "denied", reason: BRANCH_MERGED },
    ],
    [
      "refuses a branch being merged",
      { branchStatus: BranchStatus.MERGING },
      { status: "denied", reason: BRANCH_MERGING },
    ],
    [
      "allows the rebase of a branch that needs one",
      { branchStatus: BranchStatus.NEED_REBASE },
      { status: "allowed" },
    ],
    [
      "names the missing permission",
      { canRebase: false, isRunningKnown: false },
      { status: "denied", reason: REBASE_PERMISSION_DENIED },
    ],
    ["waits for the permission", { canRebase: undefined }, { status: "pending" }],
    ["waits to know whether a rebase runs", { isRunningKnown: false }, { status: "pending" }],
  ])("%s", (_, overrides, expected) => {
    expect(getRebaseAccess({ ...ALLOWED_PARAMS, ...overrides })).toEqual(expected);
  });
});

describe("getCommitLogStatus", () => {
  const ALLOWED_ACCESS: ActionAccess = { status: "allowed" };
  const toText = (parts: CommitLogTextPart[]) =>
    parts.map((part) => (typeof part === "string" ? part : part.code)).join("");
  const log = (overrides: Partial<Parameters<typeof getCommitLogStatus>[0]> = {}) => ({
    condition: RepositoryGitCondition.IN_SYNC,
    git_ref: "main",
    imported_commit: IMPORTED_HASH,
    pending_count: 0,
    ...overrides,
  });
  const behind = log({ condition: RepositoryGitCondition.BEHIND, pending_count: 3 });
  const context = (overrides: Partial<CommitLogStatusContext> = {}): CommitLogStatusContext => ({
    isReadOnly: false,
    rebaseOnly: false,
    isStaging: false,
    isActive: true,
    branchName: "feature-1",
    defaultBranchName: "trunk",
    running: null,
    repositoryAccess: ALLOWED_ACCESS,
    rebaseAccess: ALLOWED_ACCESS,
    ...overrides,
  });
  const rewritten = log({ condition: RepositoryGitCondition.REWRITTEN });
  const orphaned = log({ condition: RepositoryGitCondition.ORPHANED });

  test("offers no action when the next sync imports the pending commits", () => {
    // WHEN
    const status = getCommitLogStatus(behind, context());

    // THEN
    expect(toText(status.headline)).toBe("3 commits pending import");
    expect(toText(status.detail)).toBe("The next sync imports them, usually within a minute.");
    expect(status.tone).toBe("info");
    expect(status.primary).toBeNull();
    expect(status.secondary).toBeNull();
  });

  test("says a repository added on the branch is imported by the next sync", () => {
    // WHEN
    const status = getCommitLogStatus(behind, context({ isStaging: true }));

    // THEN
    expect(toText(status.detail)).toBe(
      "This repository was added on this branch. The next sync imports them, usually within a minute."
    );
  });

  test("offers Import latest commit and Check remote now on a read-only repository", () => {
    // WHEN
    const status = getCommitLogStatus(behind, context({ isReadOnly: true }));

    // THEN
    expect(toText(status.detail)).toBe(
      "Nothing imports a read-only repository automatically. Import the latest commit to use them."
    );
    expect(status.tone).toBe("warning");
    expect(status.primary).toEqual({ kind: "import", access: ALLOWED_ACCESS });
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test("gives the repository actions the access it is given", () => {
    // GIVEN
    const repositoryAccess: ActionAccess = { status: "denied", reason: "You need permission." };

    // WHEN
    const status = getCommitLogStatus(behind, context({ isReadOnly: true, repositoryAccess }));

    // THEN
    expect(status.primary?.access).toEqual(repositoryAccess);
    expect(status.secondary?.access).toEqual(repositoryAccess);
  });

  test("asks for a rebase on a rebase-only branch", () => {
    // GIVEN
    const rebaseAccess: ActionAccess = {
      status: "denied",
      reason: "Sign in to rebase the branch.",
    };

    // WHEN
    const status = getCommitLogStatus(behind, context({ rebaseOnly: true, rebaseAccess }));

    // THEN
    expect(toText(status.headline)).toBe("Behind main by 3 commits");
    expect(toText(status.detail)).toBe(
      "This branch does not sync with Git. A rebase moves the branch to the commit used on trunk."
    );
    expect(status.primary).toEqual({ kind: "rebase", access: rebaseAccess });
    expect(status.secondary).toBeNull();
  });

  test("says a rebase moves the branch to the commit used on the default branch while its name is unknown", () => {
    // WHEN
    const status = getCommitLogStatus(
      behind,
      context({ rebaseOnly: true, defaultBranchName: null })
    );

    // THEN
    expect(toText(status.detail)).toBe(
      "This branch does not sync with Git. A rebase moves the branch to the commit used on the default branch."
    );
  });

  test("refers to a single commit as it", () => {
    // WHEN
    const status = getCommitLogStatus({ ...behind, pending_count: 1 }, context());

    // THEN
    expect(toText(status.headline)).toBe("1 commit pending import");
    expect(toText(status.detail)).toBe("The next sync imports it, usually within a minute.");
  });

  test("says the branch is up to date with the commit it uses", () => {
    // WHEN
    const status = getCommitLogStatus(log(), context());

    // THEN
    expect(toText(status.headline)).toBe("Up to date with main");
    expect(toText(status.detail)).toBe("This branch uses the latest commit of main, aaaaaaa.");
    expect(status.tone).toBe("success");
    expect(status.secondary).toBeNull();
  });

  test("offers Check remote now on an up-to-date read-only repository", () => {
    // WHEN
    const status = getCommitLogStatus(log(), context({ isReadOnly: true }));

    // THEN
    expect(status.primary).toBeNull();
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test.each([
    RepositoryGitCondition.IN_SYNC,
    RepositoryGitCondition.BEHIND,
    RepositoryGitCondition.REWRITTEN,
    RepositoryGitCondition.ORPHANED,
    RepositoryGitCondition.REF_MISSING,
    RepositoryGitCondition.NO_REMOTE,
    RepositoryGitCondition.NOT_TRACKED,
    RepositoryGitCondition.UNAVAILABLE,
  ])(
    "offers no Check remote now for a read-only repository that is not active on the branch (%s)",
    (condition) => {
      // WHEN
      const status = getCommitLogStatus(
        log({ condition }),
        context({ isReadOnly: true, isStaging: true, isActive: false })
      );

      // THEN
      expect(status.secondary).toBeNull();
    }
  );

  test.each([RepositoryGitCondition.NOT_TRACKED, RepositoryGitCondition.UNAVAILABLE])(
    "offers Check remote now on a read-only repository whose log is %s",
    (condition) => {
      // WHEN
      const readOnly = getCommitLogStatus(log({ condition }), context({ isReadOnly: true }));
      const readWrite = getCommitLogStatus(log({ condition }), context());

      // THEN
      expect(readOnly.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
      expect(readWrite.secondary).toBeNull();
    }
  );

  test("asks to import the first commit of a read-only repository that has imported none", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.NOT_TRACKED, imported_commit: null }),
      context({ isReadOnly: true })
    );

    // THEN
    expect(toText(status.headline)).toBe("No commit imported yet");
    expect(toText(status.detail)).toBe(
      "No commit of main has been imported yet. Nothing imports a read-only repository automatically. Import the latest commit to use it."
    );
    expect(status.primary).toEqual({ kind: "import", access: ALLOWED_ACCESS });
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test("says a read-write branch tracks no remote ref, without an action", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.NOT_TRACKED }),
      context()
    );

    // THEN
    expect(toText(status.detail)).toBe("This branch tracks no remote ref.");
    expect(status.primary).toBeNull();
    expect(status.secondary).toBeNull();
  });

  test("says a rebase does not replace the branch's own commit when the branch has diverged", () => {
    // WHEN
    const status = getCommitLogStatus(rewritten, context({ rebaseOnly: true }));

    // THEN
    expect(toText(status.headline)).toBe("Diverged from main");
    expect(toText(status.detail)).toBe(
      "The commit this branch uses, aaaaaaa, is no longer in the history of main, for example after a force push. A rebase moves the branch to the commit used on trunk, unless the branch has a commit of its own in this repository."
    );
    expect(status.primary).toEqual({ kind: "rebase", access: ALLOWED_ACCESS });
    expect(status.secondary).toBeNull();
  });

  test("says the next sync imports the new head after a rewrite on a read-write repository", () => {
    // WHEN
    const status = getCommitLogStatus(rewritten, context());

    // THEN
    expect(toText(status.headline)).toBe("History of main was rewritten");
    expect(toText(status.detail)).toContain("The next sync imports the new head");
    expect(status.primary).toBeNull();
  });

  test("asks to import the new head after a rewrite on a read-only repository, without a sync", () => {
    // WHEN
    const status = getCommitLogStatus(rewritten, context({ isReadOnly: true }));

    // THEN
    expect(toText(status.detail)).toBe(
      "The commit in use, aaaaaaa, is no longer in the history of main, for example after a force push. Nothing imports a read-only repository automatically. Import the latest commit to use the new head."
    );
    expect(status.primary).toEqual({ kind: "import", access: ALLOWED_ACCESS });
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test("says the next sync imports the new head when the commit in use left the remote of a read-write repository", () => {
    // WHEN
    const status = getCommitLogStatus(orphaned, context());

    // THEN
    expect(toText(status.headline)).toBe("Commit in use not found on the remote");
    expect(toText(status.detail)).toBe(
      "The commit this branch uses, aaaaaaa, is no longer on the remote. The next sync imports the new head of main, usually within a minute."
    );
    expect(status.primary).toBeNull();
  });

  test("asks to import the new head when the commit in use left the remote of a read-only repository", () => {
    // WHEN
    const status = getCommitLogStatus(orphaned, context({ isReadOnly: true }));

    // THEN
    expect(toText(status.detail)).toBe(
      "The commit this branch uses, aaaaaaa, is no longer on the remote. Nothing imports a read-only repository automatically. Import the latest commit of main to use its new head."
    );
    expect(status.primary).toEqual({ kind: "import", access: ALLOWED_ACCESS });
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test("asks for a rebase, not a sync, when the commit in use left the remote on a rebase-only branch", () => {
    // WHEN
    const status = getCommitLogStatus(orphaned, context({ rebaseOnly: true }));

    // THEN
    expect(toText(status.detail)).toBe(
      "The commit this branch uses, aaaaaaa, is no longer on the remote. A rebase moves the branch to the commit used on trunk, unless the branch has a commit of its own in this repository."
    );
    expect(status.primary).toEqual({ kind: "rebase", access: ALLOWED_ACCESS });
    expect(status.secondary).toBeNull();
  });

  test("points to the Edit form and offers only Check remote now when the tracked ref of a read-only repository is missing", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.REF_MISSING, git_ref: "release-1" }),
      context({ isReadOnly: true })
    );

    // THEN
    expect(toText(status.headline)).toBe("release-1 no longer exists on the remote");
    expect(toText(status.detail)).toBe(
      "The branch or tag was deleted or renamed in Git, so the latest commit cannot be imported. The repository keeps using aaaaaaa. Change the tracked ref in the repository's Edit form, or restore it in Git and check the remote again."
    );
    expect(status.primary).toBeNull();
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test("asks to restore the branch or change the default branch when the ref of a read-write repository is missing", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.REF_MISSING }),
      context()
    );

    // THEN
    expect(toText(status.detail)).toBe(
      "The branch or tag was deleted or renamed in Git, so the latest commit cannot be imported. The repository keeps using aaaaaaa. Restore the branch in Git, or change the default branch of the repository."
    );
    expect(status.primary).toBeNull();
    expect(status.secondary).toBeNull();
  });

  test("asks to push the branch when the remote has no branch of its name", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.NO_REMOTE, git_ref: "feature-1" }),
      context()
    );

    // THEN
    expect(toText(status.headline)).toBe("No branch feature-1 on the remote");
    expect(status.primary).toBeNull();
  });

  test("replaces the state with the running rebase onto the default branch", () => {
    // WHEN
    const status = getCommitLogStatus(behind, context({ rebaseOnly: true, running: "rebase" }));

    // THEN
    expect(toText(status.headline)).toBe("Rebase running");
    expect(toText(status.detail)).toContain("feature-1 is being rebased on trunk,");
    expect(status.icon).toBe("running");
    expect(status.primary).toBeNull();
  });

  test("names the default branch generically while its name is unknown", () => {
    // WHEN
    const status = getCommitLogStatus(
      behind,
      context({ rebaseOnly: true, defaultBranchName: null, running: "rebase" })
    );

    // THEN
    expect(toText(status.detail)).toContain("feature-1 is being rebased on the default branch,");
  });

  test("reports an unavailable condition like an unavailable answer without a reason", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.UNAVAILABLE }),
      context()
    );

    // THEN
    expect(status).toEqual(
      getUnavailableStatus(NO_WORKER_ANSWER, { isRetrying: false, checkAction: null })
    );
  });

  test("offers no Refresh while the commit log is available", () => {
    // WHEN
    const statuses = [log(), behind, rewritten, orphaned].map((commitLog) =>
      getCommitLogStatus(commitLog, context())
    );

    // THEN
    expect(statuses.map((status) => status.canRefresh)).toEqual([false, false, false, false]);
  });
});

describe("getCheckAction", () => {
  const repositoryAccess: ActionAccess = { status: "allowed" };

  test.each([
    { isReadOnly: true, isActive: true, expected: { kind: "check", access: repositoryAccess } },
    { isReadOnly: true, isActive: false, expected: null },
    { isReadOnly: false, isActive: true, expected: null },
  ])(
    "returns $expected for a repository read-only $isReadOnly and active on the branch $isActive",
    ({ isReadOnly, isActive, expected }) => {
      expect(getCheckAction({ isReadOnly, isActive, repositoryAccess })).toEqual(expected);
    }
  );
});

describe("getUnavailableStatus", () => {
  const emptyState = {
    title: "Commit log not available yet",
    message: "Use the refresh button to check again.",
  };
  const checkAction = { kind: "check" as const, access: { status: "allowed" as const } };

  test("offers Refresh and Check remote now once retrying has stopped", () => {
    // WHEN
    const status = getUnavailableStatus(emptyState, { isRetrying: false, checkAction });

    // THEN
    expect(status.headline).toEqual(["Commit log not available yet"]);
    expect(status.canRefresh).toBe(true);
    expect(status.secondary).toEqual(checkAction);
  });

  test("shows a spinner and no action while it retries", () => {
    // WHEN
    const status = getUnavailableStatus(emptyState, { isRetrying: true, checkAction });

    // THEN
    expect(status.icon).toBe("running");
    expect(status.canRefresh).toBe(false);
    expect(status.secondary).toBeNull();
  });
});

describe("getDeniedReasons", () => {
  test("lists each reason once, in the order of the actions, and skips allowed or pending actions", () => {
    // GIVEN
    const denied = (reason: string): ActionAccess => ({ status: "denied", reason });

    // WHEN
    const reasons = getDeniedReasons([
      { kind: "check", access: denied("No update permission.") },
      { kind: "import", access: denied("No update permission.") },
      { kind: "check", access: { status: "allowed" } },
      { kind: "rebase", access: { status: "pending" } },
      null,
      { kind: "check", access: denied("No default branch permission.") },
    ]);

    // THEN
    expect(reasons).toEqual(["No update permission.", "No default branch permission."]);
  });
});

describe("getReasonId", () => {
  const deniedReasons = ["Sign in to change this repository.", "You need permission."];

  test("points a denied action to the line of its reason", () => {
    // WHEN
    const id = getReasonId(
      { kind: "import", access: { status: "denied", reason: "You need permission." } },
      deniedReasons,
      "reasons"
    );

    // THEN
    expect(id).toBe("reasons-1");
  });

  test.each<ActionAccess>([{ status: "allowed" }, { status: "pending" }])(
    "gives no id to an action that is $status",
    (access) => {
      expect(getReasonId({ kind: "import", access }, deniedReasons, "reasons")).toBeUndefined();
    }
  );
});

describe("mayKeepOwnCommit", () => {
  test.each([
    [RepositoryGitCondition.REWRITTEN, true],
    [RepositoryGitCondition.ORPHANED, true],
    [RepositoryGitCondition.BEHIND, false],
    [RepositoryGitCondition.IN_SYNC, false],
    [null, false],
  ])("returns %j for %s", (condition, expected) => {
    expect(mayKeepOwnCommit(condition)).toBe(expected);
  });
});

describe("isErrorWithoutClientToast", () => {
  const thrownByTransport = (...graphQLErrors: GraphQLError[]) =>
    new Error("Request failed", { cause: new CombinedError({ graphQLErrors }) });
  const permissionDenial = () =>
    new GraphQLError("Denied", { extensions: { code: ERROR_CODES.PERMISSION_DENIED } });

  test.each([
    { case: "a permission denial", error: thrownByTransport(permissionDenial()), expected: true },
    { case: "a network error", error: new TypeError("Failed to fetch"), expected: true },
    {
      case: "another GraphQL error",
      error: thrownByTransport(new GraphQLError("Database unavailable")),
      expected: false,
    },
    {
      case: "a permission denial that comes with another GraphQL error",
      error: thrownByTransport(permissionDenial(), new GraphQLError("Database unavailable")),
      expected: false,
    },
  ])("returns $expected for $case", ({ error, expected }) => {
    expect(isErrorWithoutClientToast(error)).toBe(expected);
  });
});

describe("getCommitLogHeaderState", () => {
  const unavailableLog = {
    repository_id: "repo-1",
    branch_name: "main",
    git_ref: "main",
    condition: RepositoryGitCondition.UNAVAILABLE,
    imported_commit: null,
    remote_head: null,
    pending_count: null,
    fetched_at: null,
    checked_at: null,
    unavailable: { reason: RepositoryGitUnavailableReason.NOT_CLONED, message: "Not cloned yet." },
    commits: [],
  };

  test("shows a loaded log whatever the state of its first read", () => {
    // WHEN
    const state = getCommitLogHeaderState(unavailableLog, {
      kind: "failed",
      error: new Error("x"),
    });

    // THEN
    expect(state).toEqual({ kind: "loaded", log: unavailableLog });
  });

  test("explains an unavailable answer with its empty state", () => {
    // GIVEN
    const error = new RepositoryGitUnavailableError(unavailableLog);

    // WHEN
    const state = getCommitLogHeaderState(undefined, {
      kind: "unavailable",
      error,
      isRetrying: false,
    });

    // THEN
    expect(state).toEqual({
      kind: "unavailable",
      log: unavailableLog,
      emptyState: getEmptyState(error, { isRetrying: false }),
      isRetrying: false,
    });
  });

  test.each(["failed", "loading"] as const)("passes on a %s first read", (kind) => {
    // WHEN
    const state = getCommitLogHeaderState(
      undefined,
      kind === "failed" ? { kind, error: new Error("x") } : { kind }
    );

    // THEN
    expect(state).toEqual({ kind });
  });
});
