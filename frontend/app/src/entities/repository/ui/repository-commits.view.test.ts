import { describe, expect, test } from "vitest";

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
  type CommitLogStatusContext,
  type CommitLogTextPart,
  canLoadOlderCommits,
  DEFAULT_BRANCH_EDIT_DENIED,
  formatCommitsTabCount,
  getCommitLogHeaderState,
  getCommitLogStatus,
  getCommitLogWithoutPages,
  getCommitsTabBadge,
  getDeniedReasons,
  getEmptyState,
  getFreshness,
  getLoadedCommits,
  getNextPageState,
  getRebaseAccess,
  getRepositoryActionAccess,
  getStateBadges,
  getUnavailableStatus,
  isLoadingFirstPage,
  isShowingStaleCommits,
  NO_WORKER_ANSWER,
  REBASE_DEFAULT_BRANCH,
  REBASE_MERGED_BRANCH,
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
      message: "Not cloned. Refresh to check again.",
    });
  });

  test("says no worker answered and asks for a refresh once retrying an answer without a reason has stopped", () => {
    // WHEN
    const emptyState = getEmptyState({ reason: null, message: "No answer" }, { isRetrying: false });

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
      tooltip: "1 commit behind release-1.4 — rebase the branch to use it",
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
        "This branch has diverged from main. Rebase the branch to use the latest commit of main.",
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
        updatePermission: DENIED,
        isDefaultBranch: true,
        canEditDefaultBranch: false,
      },
      expected: { status: "denied", reason: REPOSITORY_SIGN_IN_REQUIRED },
    },
    {
      case: "allows an update on the default branch with both permissions",
      params: {
        isAuthenticated: true,
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

describe("getRebaseAccess", () => {
  const ALLOWED_PARAMS: Parameters<typeof getRebaseAccess>[0] = {
    isAuthenticated: true,
    isDefaultBranch: false,
    isMerged: false,
    canRebase: true,
    isRunningKnown: true,
  };

  test.each<[string, Partial<Parameters<typeof getRebaseAccess>[0]>, ActionAccess]>([
    ["allows a signed-in user with the permission", {}, { status: "allowed" }],
    [
      "asks to sign in before checking anything else",
      { isAuthenticated: false, isDefaultBranch: true, isMerged: true, canRebase: false },
      { status: "denied", reason: REBASE_SIGN_IN_REQUIRED },
    ],
    [
      "refuses the default branch",
      { isDefaultBranch: true },
      { status: "denied", reason: REBASE_DEFAULT_BRANCH },
    ],
    [
      "refuses a merged branch",
      { isMerged: true },
      { status: "denied", reason: REBASE_MERGED_BRANCH },
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
  const LOCATION = "https://github.com/opsmill/infrahub-demo.git";
  const ALLOWED_ACCESS: ActionAccess = { status: "allowed" };
  const toText = (parts: CommitLogTextPart[]) =>
    parts.map((part) => (typeof part === "string" ? part : part.code)).join("");
  const log = (overrides: Partial<Parameters<typeof getCommitLogStatus>[0]> = {}) => ({
    condition: RepositoryGitCondition.IN_SYNC,
    git_ref: "main",
    imported_commit: IMPORTED_HASH,
    remote_head: IMPORTED_HASH,
    pending_count: 0,
    ...overrides,
  });
  const behind = log({
    condition: RepositoryGitCondition.BEHIND,
    remote_head: OTHER_HASH,
    pending_count: 3,
  });
  const context = (overrides: Partial<CommitLogStatusContext> = {}): CommitLogStatusContext => ({
    isReadOnly: false,
    rebaseOnly: false,
    isStaging: false,
    branchName: "feature-1",
    defaultBranchName: "trunk",
    repositoryLocation: LOCATION,
    running: null,
    repositoryAccess: ALLOWED_ACCESS,
    rebaseAccess: ALLOWED_ACCESS,
    ...overrides,
  });
  const latestCommit = {
    kind: "latest-commit",
    url: `https://github.com/opsmill/infrahub-demo/commit/${OTHER_HASH}`,
  };
  const rewritten = log({ condition: RepositoryGitCondition.REWRITTEN, remote_head: OTHER_HASH });
  const orphaned = log({ condition: RepositoryGitCondition.ORPHANED, remote_head: OTHER_HASH });

  test("offers no action when the next sync imports the pending commits", () => {
    // WHEN
    const status = getCommitLogStatus(behind, context());

    // THEN
    expect(toText(status.headline)).toBe("3 commits pending import");
    expect(toText(status.detail)).toBe("The next sync imports them, usually within a minute.");
    expect(status.tone).toBe("info");
    expect(status.primary).toBeNull();
    expect(status.secondary).toBeNull();
    expect(status.links).toEqual([{ kind: "repository-tasks" }, latestCommit]);
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

  test("asks for a rebase and links the branch and the comparison on a rebase-only branch", () => {
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
      "This branch does not sync with Git, so only a rebase of the branch brings them."
    );
    expect(status.primary).toEqual({ kind: "rebase", access: rebaseAccess });
    expect(status.secondary).toBeNull();
    expect(status.links).toEqual([
      { kind: "branch", branchName: "feature-1" },
      {
        kind: "compare",
        url: `https://github.com/opsmill/infrahub-demo/compare/${IMPORTED_HASH}...${OTHER_HASH}`,
      },
    ]);
  });

  test("offers Check remote now beside the rebase of a read-only repository behind its ref", () => {
    // WHEN
    const status = getCommitLogStatus(behind, context({ rebaseOnly: true, isReadOnly: true }));

    // THEN
    expect(status.primary).toEqual({ kind: "rebase", access: ALLOWED_ACCESS });
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
  });

  test("refers to a single commit as it", () => {
    // WHEN
    const status = getCommitLogStatus({ ...behind, pending_count: 1 }, context());

    // THEN
    expect(toText(status.headline)).toBe("1 commit pending import");
    expect(toText(status.detail)).toBe("The next sync imports it, usually within a minute.");
  });

  test("leaves the GitHub links out for a remote that is not on GitHub", () => {
    // WHEN
    const status = getCommitLogStatus(
      behind,
      context({ rebaseOnly: true, repositoryLocation: "https://gitlab.com/opsmill/demo.git" })
    );

    // THEN
    expect(status.links).toEqual([{ kind: "branch", branchName: "feature-1" }]);
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

  test.each([false, true])(
    "offers Check remote now on an up-to-date read-only repository (rebase-only: %s)",
    (rebaseOnly) => {
      // WHEN
      const status = getCommitLogStatus(log(), context({ isReadOnly: true, rebaseOnly }));

      // THEN
      expect(status.primary).toBeNull();
      expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
    }
  );

  test("says a rebase does not replace the branch's own commit when the branch has diverged", () => {
    // WHEN
    const status = getCommitLogStatus(rewritten, context({ rebaseOnly: true }));

    // THEN
    expect(toText(status.headline)).toBe("Diverged from main");
    expect(toText(status.detail)).toBe(
      "The commit this branch uses, aaaaaaa, is no longer in the history of main, for example after a force push. A rebase moves the branch to the latest commit of main, unless the branch has a commit of its own in this repository."
    );
    expect(status.primary).toEqual({ kind: "rebase", access: ALLOWED_ACCESS });
  });

  test.each([
    ["rewritten", rewritten],
    ["orphaned", orphaned],
  ])(
    "offers Check remote now beside the rebase of a %s read-only repository, and not of a read-write one",
    (_, condition) => {
      // WHEN
      const readOnly = getCommitLogStatus(
        condition,
        context({ rebaseOnly: true, isReadOnly: true })
      );
      const readWrite = getCommitLogStatus(condition, context({ rebaseOnly: true }));

      // THEN
      expect(readOnly.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
      expect(readWrite.secondary).toBeNull();
    }
  );

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
    const status = getCommitLogStatus(orphaned, context({ rebaseOnly: true, isReadOnly: true }));

    // THEN
    expect(toText(status.detail)).toBe(
      "The commit this branch uses, aaaaaaa, is no longer on the remote. A rebase moves the branch to the latest commit of main, unless the branch has a commit of its own in this repository."
    );
    expect(status.primary).toEqual({ kind: "rebase", access: ALLOWED_ACCESS });
    expect(status.secondary).toEqual({ kind: "check", access: ALLOWED_ACCESS });
    expect(status.links).toEqual([{ kind: "branch", branchName: "feature-1" }]);
  });

  test("offers Change tracked ref, not Import latest commit, when the tracked ref is missing", () => {
    // WHEN
    const status = getCommitLogStatus(
      log({ condition: RepositoryGitCondition.REF_MISSING, git_ref: "release-1" }),
      context({ isReadOnly: true })
    );

    // THEN
    expect(toText(status.headline)).toBe("release-1 no longer exists on the remote");
    expect(status.primary).toEqual({ kind: "change-ref", access: ALLOWED_ACCESS });
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
    expect(status.links).toEqual([]);
  });

  test("replaces the state with the running rebase onto the default branch and links its task", () => {
    // WHEN
    const status = getCommitLogStatus(
      behind,
      context({ rebaseOnly: true, running: { action: "rebase", taskId: "task-1" } })
    );

    // THEN
    expect(toText(status.headline)).toBe("Rebase running");
    expect(toText(status.detail)).toContain("feature-1 is being rebased on trunk,");
    expect(status.icon).toBe("running");
    expect(status.primary).toBeNull();
    expect(status.links).toEqual([
      { kind: "task", taskId: "task-1" },
      { kind: "branch", branchName: "feature-1" },
    ]);
  });

  test("names the default branch generically while its name is unknown", () => {
    // WHEN
    const status = getCommitLogStatus(
      behind,
      context({
        rebaseOnly: true,
        defaultBranchName: null,
        running: { action: "rebase", taskId: null },
      })
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
    expect(status).toEqual(getUnavailableStatus(NO_WORKER_ANSWER, { isRetrying: false }));
  });
});

describe("getUnavailableStatus", () => {
  const emptyState = { title: "Commit log not available yet", message: "Refresh to check again." };

  test("offers Refresh once retrying has stopped", () => {
    // WHEN
    const status = getUnavailableStatus(emptyState, { isRetrying: false });

    // THEN
    expect(status.headline).toEqual(["Commit log not available yet"]);
    expect(status.secondary).toEqual({ kind: "refresh", access: { status: "allowed" } });
  });

  test("shows a spinner and no action while it retries", () => {
    // WHEN
    const status = getUnavailableStatus(emptyState, { isRetrying: true });

    // THEN
    expect(status.icon).toBe("running");
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
      { kind: "refresh", access: { status: "allowed" } },
      { kind: "rebase", access: { status: "pending" } },
      null,
      { kind: "change-ref", access: denied("No default branch permission.") },
    ]);

    // THEN
    expect(reasons).toEqual(["No update permission.", "No default branch permission."]);
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
