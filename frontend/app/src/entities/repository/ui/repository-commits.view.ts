import type { BadgeProps } from "@/shared/components/ui/badge";
import { warnUnexpectedType } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import {
  type RepositoryCommit,
  type RepositoryCommitLog,
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";

// Offset paging over a moving log can repeat a commit at a page boundary.
export function getLoadedCommits(
  pages: Pick<RepositoryCommitLog, "commits">[]
): RepositoryCommit[] {
  return [
    ...new Map(
      pages.flatMap((page) => page.commits).map((commit) => [commit.hash, commit])
    ).values(),
  ];
}

export type CommitLogWithoutPages =
  | { kind: "loading" }
  | { kind: "unavailable"; error: RepositoryGitUnavailableError; isRetrying: boolean }
  | { kind: "failed"; error: Error };

interface CommitLogFailure {
  error: Error | null;
  failureReason: Error | null;
}

// A retried attempt only reports its failure through failureReason; error stays null until retrying stops.
export function getCommitLogWithoutPages({
  error,
  failureReason,
  isFetching,
}: CommitLogFailure & { isFetching: boolean }): CommitLogWithoutPages {
  const failure = error ?? failureReason;
  if (failure instanceof RepositoryGitUnavailableError)
    return { kind: "unavailable", error: failure, isRetrying: isFetching };
  if (failure) return { kind: "failed", error: failure };
  return { kind: "loading" };
}

export function isLoadingFirstPage({
  isPending,
  failureReason,
}: Pick<CommitLogFailure, "failureReason"> & { isPending: boolean }): boolean {
  return isPending && failureReason === null;
}

export function isShowingStaleCommits({
  isRefetchError,
  isRefetching,
  failureReason,
}: Pick<CommitLogFailure, "failureReason"> & {
  isRefetchError: boolean;
  isRefetching: boolean;
}): boolean {
  return (isRefetchError && !isRefetching) || (isRefetching && failureReason !== null);
}

// Older pages are read at offsets of the current history, so they must not be appended to a first page
// that a failed or running refresh has left out of date.
export function canLoadOlderCommits({
  hasNextPage,
  isRefetching,
  isRefetchError,
}: {
  hasNextPage: boolean;
  isRefetching: boolean;
  isRefetchError: boolean;
}): boolean {
  return hasNextPage && !isRefetching && !isRefetchError;
}

export type NextPageState = "idle" | "loading" | "failed" | "retry-pending";

export function getNextPageState({
  isFetchNextPageError,
  isFetchingNextPage,
  failureReason,
}: Pick<CommitLogFailure, "failureReason"> & {
  isFetchNextPageError: boolean;
  isFetchingNextPage: boolean;
}): NextPageState {
  if (!isFetchingNextPage) return isFetchNextPageError ? "failed" : "idle";
  // Pressing Retry while the query still retries on its own would cancel that retry.
  return failureReason !== null ? "retry-pending" : "loading";
}

export interface RepositoryCommitsRepository {
  id: string;
  name: string;
  isReadOnly: boolean;
  isStaging: boolean;
  updatePermission: PermissionDecision;
}

export type CommitLogHeaderState =
  | { kind: "loading" }
  | { kind: "failed" }
  | {
      kind: "unavailable";
      log: RepositoryCommitLog;
      emptyState: CommitLogEmptyState;
      isRetrying: boolean;
    }
  | { kind: "loaded"; log: RepositoryCommitLog };

export function getCommitLogHeaderState(
  log: RepositoryCommitLog | undefined,
  withoutPages: CommitLogWithoutPages
): CommitLogHeaderState {
  if (log) return { kind: "loaded", log };
  switch (withoutPages.kind) {
    case "unavailable":
      return {
        kind: "unavailable",
        log: withoutPages.error.log,
        emptyState: getEmptyState(withoutPages.error, { isRetrying: withoutPages.isRetrying }),
        isRetrying: withoutPages.isRetrying,
      };
    case "failed":
      return { kind: "failed" };
    default:
      return { kind: "loading" };
  }
}

export interface CommitLogEmptyState {
  title: string;
  message: string;
}

export const NO_WORKER_ANSWER: CommitLogEmptyState = {
  title: "Commit log not available yet",
  message: "No worker has answered yet. Refresh to check again.",
};

export function getEmptyState(
  { reason, message }: Pick<RepositoryGitUnavailableError, "reason" | "message">,
  { isRetrying }: { isRetrying: boolean }
): CommitLogEmptyState {
  if (reason === RepositoryGitUnavailableReason.NOT_IMPLEMENTED) {
    return {
      title: "Commit log not available",
      message: message || "Reading commits is not available in this version of Infrahub.",
    };
  }
  if (!isRetrying && reason === RepositoryGitUnavailableReason.NOT_CLONED) {
    return {
      title: "Commit log not available yet",
      message: `${message || "No worker holds a copy of this repository yet."} Refresh to check again.`,
    };
  }
  if (!isRetrying) return NO_WORKER_ANSWER;
  return {
    title: "Commit log not available yet",
    message: message || "Waiting for a worker to answer.",
  };
}

export interface CommitStateBadge {
  label: string;
  variant: BadgeProps["variant"];
}

const REMOTE_HEAD_BADGE: CommitStateBadge = { label: "Remote head", variant: "blue" };
const IMPORTED_BADGE: CommitStateBadge = { label: "Imported", variant: "green" };
const PENDING_BADGE: CommitStateBadge = { label: "Pending import", variant: "yellow" };
const UNRELATED_BADGE: CommitStateBadge = {
  label: "Not on current history",
  variant: "gray-outline",
};
const BEHIND_BADGE: CommitStateBadge = { label: "Behind", variant: "gray" };

export interface CommitBadgeContext extends Pick<RepositoryCommitLog, "condition"> {
  importedCommit: string | null;
  rebaseOnly: boolean;
}

export function getStateBadges(
  { hash, state }: Pick<RepositoryCommit, "hash" | "state">,
  { importedCommit, condition, rebaseOnly }: CommitBadgeContext
): CommitStateBadge[] {
  switch (state) {
    case RepositoryCommitState.HEAD:
      if (hash === importedCommit) return [REMOTE_HEAD_BADGE, IMPORTED_BADGE];
      // Only BEHIND guarantees the head is newer than the branch's commit; after a reset it can be an ancestor.
      return rebaseOnly && condition === RepositoryGitCondition.BEHIND
        ? [REMOTE_HEAD_BADGE, BEHIND_BADGE]
        : [REMOTE_HEAD_BADGE];
    case RepositoryCommitState.NOT_ON_BRANCH:
      return [BEHIND_BADGE];
    case RepositoryCommitState.IMPORTED:
      return [IMPORTED_BADGE];
    case RepositoryCommitState.PENDING:
      return [PENDING_BADGE];
    case RepositoryCommitState.UNRELATED:
      return [UNRELATED_BADGE];
    case RepositoryCommitState.HISTORY:
      return [];
    default:
      warnUnexpectedType(state);
      return [];
  }
}

export interface CommitLogFreshness {
  trackedRef: string | null;
  checkedAt: string | null;
  updatedAt: string | null;
}

export function getFreshness({
  git_ref,
  checked_at,
  fetched_at,
}: Pick<RepositoryCommitLog, "git_ref" | "checked_at" | "fetched_at">): CommitLogFreshness {
  return {
    trackedRef: git_ref,
    checkedAt: checked_at,
    // fetched_at equals checked_at when the last check fetched new commits, so show the time once.
    updatedAt: fetched_at === checked_at ? null : fetched_at,
  };
}

const getRefName = (gitRef: string | null) => gitRef ?? "the default branch";

export const REPOSITORY_SIGN_IN_REQUIRED = "Sign in to change this repository.";
export const DEFAULT_BRANCH_EDIT_DENIED = "You need permission to edit the default branch.";

/** Whether the user may run an action now; pending while what decides it is still loading. */
export type ActionAccess =
  | { status: "allowed" }
  | { status: "pending" }
  | { status: "denied"; reason: string };

const ALLOWED: ActionAccess = { status: "allowed" };
const PENDING: ActionAccess = { status: "pending" };

export function getRepositoryActionAccess({
  isAuthenticated,
  updatePermission,
  isDefaultBranch,
  canEditDefaultBranch,
}: {
  isAuthenticated: boolean;
  updatePermission: PermissionDecision;
  isDefaultBranch: boolean;
  /** Undefined while the permission is loading. */
  canEditDefaultBranch: boolean | undefined;
}): ActionAccess {
  if (!isAuthenticated) return { status: "denied", reason: REPOSITORY_SIGN_IN_REQUIRED };
  if (!updatePermission.isAllowed) return { status: "denied", reason: updatePermission.message };
  if (isDefaultBranch && canEditDefaultBranch === false) {
    return { status: "denied", reason: DEFAULT_BRANCH_EDIT_DENIED };
  }
  if (isDefaultBranch && canEditDefaultBranch === undefined) return PENDING;
  return ALLOWED;
}

export const REBASE_SIGN_IN_REQUIRED = "Sign in to rebase the branch.";
export const REBASE_DEFAULT_BRANCH = "The default branch cannot be rebased.";
export const REBASE_MERGED_BRANCH = "A merged branch cannot be rebased.";
export const REBASE_PERMISSION_DENIED = "You need permission to rebase branches.";

export function getRebaseAccess({
  isAuthenticated,
  isDefaultBranch,
  isMerged,
  canRebase,
  isRunningKnown,
}: {
  isAuthenticated: boolean;
  isDefaultBranch: boolean;
  isMerged: boolean;
  /** Undefined while the permission is loading. */
  canRebase: boolean | undefined;
  /** False until the lookup of a running rebase answers, so a second rebase is not offered meanwhile. */
  isRunningKnown: boolean;
}): ActionAccess {
  if (!isAuthenticated) return { status: "denied", reason: REBASE_SIGN_IN_REQUIRED };
  if (isDefaultBranch) return { status: "denied", reason: REBASE_DEFAULT_BRANCH };
  if (isMerged) return { status: "denied", reason: REBASE_MERGED_BRANCH };
  if (canRebase === false) return { status: "denied", reason: REBASE_PERMISSION_DENIED };
  if (canRebase === undefined || !isRunningKnown) return PENDING;
  return ALLOWED;
}

export type CommitLogStatusTone = "success" | "info" | "warning" | "neutral";

export type CommitLogStatusIcon =
  | "in-sync"
  | "pending-import"
  | "behind"
  | "warning"
  | "unknown"
  | "running";

export type CommitLogActionKind = "import" | "rebase" | "check" | "refresh";

/** A ref name or a commit hash is rendered as code. */
export type CommitLogTextPart = string | { code: string };

export interface CommitLogAction {
  kind: CommitLogActionKind;
  access: ActionAccess;
}

export function getDeniedReason(action: CommitLogAction | null): string | null {
  return action?.access.status === "denied" ? action.access.reason : null;
}

/** The distinct reasons the given actions are denied, in order. */
export function getDeniedReasons(actions: (CommitLogAction | null)[]): string[] {
  const reasons = actions
    .map(getDeniedReason)
    .filter((reason): reason is string => reason !== null);
  return [...new Set(reasons)];
}

export interface CommitLogStatus {
  tone: CommitLogStatusTone;
  icon: CommitLogStatusIcon;
  headline: CommitLogTextPart[];
  detail: CommitLogTextPart[];
  primary: CommitLogAction | null;
  secondary: CommitLogAction | null;
}

export interface CommitLogStatusContext {
  isReadOnly: boolean;
  rebaseOnly: boolean;
  /** The repository was added on this branch and is not on the default branch yet. */
  isStaging: boolean;
  branchName: string;
  /** Infrahub's default branch, which a rebase moves the branch onto; null while unknown. */
  defaultBranchName: string | null;
  running: "rebase" | "import" | null;
  repositoryAccess: ActionAccess;
  rebaseAccess: ActionAccess;
}

function getDefaultBranchPart(defaultBranchName: string | null): CommitLogTextPart {
  return defaultBranchName ? { code: defaultBranchName } : "the default branch";
}

const NO_ACTION = { primary: null, secondary: null };

const SHORT_HASH_LENGTH = 7;

export function getCommitLogStatus(
  {
    condition,
    git_ref,
    imported_commit,
    pending_count,
  }: Pick<RepositoryCommitLog, "condition" | "git_ref" | "imported_commit" | "pending_count">,
  context: CommitLogStatusContext
): CommitLogStatus {
  const { isReadOnly, rebaseOnly, isStaging, branchName, running } = context;
  const ref = { code: getRefName(git_ref) };
  const used = imported_commit ? { code: imported_commit.slice(0, SHORT_HASH_LENGTH) } : null;
  const usedAside = used ? [", ", used, ","] : [];
  const them = pending_count === 1 ? "it" : "them";

  const importAction: CommitLogAction = { kind: "import", access: context.repositoryAccess };
  const checkAction: CommitLogAction = { kind: "check", access: context.repositoryAccess };
  const rebaseAction: CommitLogAction = { kind: "rebase", access: context.rebaseAccess };
  const rebaseMovesToLatest = [
    " A rebase moves the branch to the latest commit of ",
    ref,
    ", unless the branch has a commit of its own in this repository.",
  ];

  if (running === "rebase") {
    return {
      ...NO_ACTION,
      tone: "info",
      icon: "running",
      headline: ["Rebase running"],
      detail: [
        { code: branchName },
        " is being rebased on ",
        getDefaultBranchPart(context.defaultBranchName),
        ", with all its data and all its repositories. The commit log updates when the rebase ends.",
      ],
    };
  }
  if (running === "import") {
    return {
      ...NO_ACTION,
      tone: "info",
      icon: "running",
      headline: ["Import running"],
      detail: [
        "The latest commit of ",
        ref,
        " is being imported. The commit log updates when the import ends.",
      ],
    };
  }

  switch (condition) {
    case RepositoryGitCondition.IN_SYNC:
      return {
        tone: "success",
        icon: "in-sync",
        headline: ["Up to date with ", ref],
        detail: [
          rebaseOnly
            ? "This branch does not sync with Git and uses the latest commit of "
            : "This branch uses the latest commit of ",
          ref,
          ...(used ? [", ", used, "."] : ["."]),
        ],
        primary: null,
        secondary: isReadOnly ? checkAction : null,
      };
    case RepositoryGitCondition.BEHIND:
      if (rebaseOnly) {
        return {
          tone: "warning",
          icon: "behind",
          headline:
            pending_count === null
              ? ["Behind ", ref]
              : ["Behind ", ref, ` by ${formatCommitCount(pending_count)}`],
          detail: [
            `This branch does not sync with Git, so only a rebase of the branch brings ${them}.`,
          ],
          primary: rebaseAction,
          secondary: isReadOnly ? checkAction : null,
        };
      }
      if (isReadOnly) {
        return {
          tone: "warning",
          icon: "pending-import",
          headline: [getPendingImportHeadline(pending_count)],
          detail: [
            `Nothing imports a read-only repository automatically. Import the latest commit to use ${them}.`,
          ],
          primary: importAction,
          secondary: checkAction,
        };
      }
      return {
        ...NO_ACTION,
        tone: "info",
        icon: "pending-import",
        headline: [getPendingImportHeadline(pending_count)],
        detail: [
          isStaging
            ? `This repository was added on this branch. The next sync imports ${them}, usually within a minute.`
            : `The next sync imports ${them}, usually within a minute.`,
        ],
      };
    case RepositoryGitCondition.REWRITTEN: {
      const lostFromHistory = [
        " is no longer in the history of ",
        ref,
        ", for example after a force push.",
      ];
      if (rebaseOnly) {
        return {
          tone: "warning",
          icon: "warning",
          headline: ["Diverged from ", ref],
          detail: [
            "The commit this branch uses",
            ...usedAside,
            ...lostFromHistory,
            ...rebaseMovesToLatest,
          ],
          primary: rebaseAction,
          secondary: isReadOnly ? checkAction : null,
        };
      }
      if (isReadOnly) {
        return {
          tone: "warning",
          icon: "warning",
          headline: ["History of ", ref, " was rewritten"],
          detail: [
            "The commit in use",
            ...usedAside,
            ...lostFromHistory,
            " Nothing imports a read-only repository automatically. Import the latest commit to use the new head.",
          ],
          primary: importAction,
          secondary: checkAction,
        };
      }
      return {
        ...NO_ACTION,
        tone: "warning",
        icon: "warning",
        headline: ["History of ", ref, " was rewritten"],
        detail: [
          "The commit in use",
          ...usedAside,
          ...lostFromHistory,
          " The next sync imports the new head, usually within a minute.",
        ],
      };
    }
    case RepositoryGitCondition.ORPHANED: {
      const headline = ["Commit in use not found on the remote"];
      const lostFromRemote = [
        "The commit this branch uses",
        ...usedAside,
        " is no longer on the remote.",
      ];
      if (rebaseOnly) {
        return {
          tone: "warning",
          icon: "warning",
          headline,
          detail: [...lostFromRemote, ...rebaseMovesToLatest],
          primary: rebaseAction,
          secondary: isReadOnly ? checkAction : null,
        };
      }
      if (isReadOnly) {
        return {
          tone: "warning",
          icon: "warning",
          headline,
          detail: [
            ...lostFromRemote,
            " Nothing imports a read-only repository automatically. Import the latest commit of ",
            ref,
            " to use its new head.",
          ],
          primary: importAction,
          secondary: checkAction,
        };
      }
      return {
        ...NO_ACTION,
        tone: "warning",
        icon: "warning",
        headline,
        detail: [
          ...lostFromRemote,
          " The next sync imports the new head of ",
          ref,
          ", usually within a minute.",
        ],
      };
    }
    case RepositoryGitCondition.REF_MISSING:
      return {
        tone: "warning",
        icon: "warning",
        headline: [ref, " no longer exists on the remote"],
        detail: [
          "The branch or tag was deleted or renamed in Git, so the latest commit cannot be imported. ",
          ...(used
            ? ["The repository keeps using ", used, "."]
            : ["The repository keeps using the commit it imported last."]),
          isReadOnly
            ? " Change the tracked ref in the repository's Edit form, or restore it in Git and check the remote again."
            : " Restore the branch in Git, or change the default branch of the repository.",
        ],
        primary: null,
        secondary: isReadOnly ? checkAction : null,
      };
    case RepositoryGitCondition.NO_REMOTE:
      return {
        ...NO_ACTION,
        tone: "neutral",
        icon: "unknown",
        headline: ["No branch ", ref, " on the remote"],
        detail: [
          "This branch syncs with Git, but the remote has no branch with this name. Push the branch to the remote; the next sync then imports its commits.",
        ],
      };
    case RepositoryGitCondition.NOT_TRACKED:
      return {
        ...NO_ACTION,
        tone: "neutral",
        icon: "unknown",
        headline: ["No commit log"],
        detail: ["This branch tracks no remote ref."],
      };
    case RepositoryGitCondition.UNAVAILABLE:
      return getUnavailableStatus(NO_WORKER_ANSWER, { isRetrying: false });
    default:
      warnUnexpectedType(condition);
      return {
        ...NO_ACTION,
        tone: "neutral",
        icon: "unknown",
        headline: ["Commit log"],
        detail: [],
      };
  }
}

export function getUnavailableStatus(
  { title, message }: CommitLogEmptyState,
  { isRetrying }: { isRetrying: boolean }
): CommitLogStatus {
  return {
    tone: "neutral",
    icon: isRetrying ? "running" : "unknown",
    headline: [title],
    detail: [message],
    primary: null,
    secondary: isRetrying ? null : { kind: "refresh", access: ALLOWED },
  };
}

function getPendingImportHeadline(pendingCount: number | null): string {
  return pendingCount === null
    ? "New commits pending import"
    : `${formatCommitCount(pendingCount)} pending import`;
}

const COMMITS_TAB_COUNT_CAP = 999;

export type CommitsTabBadge =
  | { kind: "pending-import" | "behind"; count: number; summary: string; tooltip: string }
  | { kind: "warning"; summary: string; tooltip: string };

export function formatCommitsTabCount(count: number): string {
  return count > COMMITS_TAB_COUNT_CAP ? `${COMMITS_TAB_COUNT_CAP}+` : `${count}`;
}

export function getCommitsTabBadge(
  {
    condition,
    git_ref,
    pending_count,
  }: Pick<RepositoryCommitLog, "condition" | "git_ref" | "pending_count">,
  { rebaseOnly, isReadOnly }: Pick<CommitBadgeContext, "rebaseOnly"> & { isReadOnly: boolean }
): CommitsTabBadge | null {
  const ref = getRefName(git_ref);
  switch (condition) {
    case RepositoryGitCondition.BEHIND: {
      if (!pending_count) return null;
      const pronoun = pending_count === 1 ? "it" : "them";
      if (rebaseOnly) {
        const summary = `${formatCommitCount(pending_count)} behind ${ref}`;
        return {
          kind: "behind",
          count: pending_count,
          summary,
          tooltip: `${summary} — rebase the branch to use ${pronoun}`,
        };
      }
      const summary = `${formatCommitCount(pending_count)} pending import`;
      // Nothing imports a read-only repository on its own; its periodic check only notices that the ref moved.
      const action = isReadOnly
        ? `run Import latest commit to use ${pronoun}`
        : `the next sync imports ${pronoun}`;
      return {
        kind: "pending-import",
        count: pending_count,
        summary,
        tooltip: `${summary} — ${action}`,
      };
    }
    case RepositoryGitCondition.REWRITTEN:
      return rebaseOnly
        ? {
            kind: "warning",
            summary: `diverged from ${ref}`,
            tooltip: `This branch has diverged from ${ref}. Rebase the branch to use the latest commit of ${ref}.`,
          }
        : {
            kind: "warning",
            summary: "history rewritten",
            tooltip: "The tracked ref was rewritten, so nothing is reported as pending import.",
          };
    case RepositoryGitCondition.ORPHANED:
      return {
        kind: "warning",
        summary: "imported commit missing",
        tooltip: "The imported commit could not be found on the remote.",
      };
    case RepositoryGitCondition.REF_MISSING:
      return {
        kind: "warning",
        summary: "tracked ref missing",
        tooltip:
          "The tracked branch or tag no longer exists on the remote. The imported commit is still in use.",
      };
    default:
      return null;
  }
}

function formatCommitCount(count: number): string {
  return `${formatNumberDisplay(count)} ${count === 1 ? "commit" : "commits"}`;
}
