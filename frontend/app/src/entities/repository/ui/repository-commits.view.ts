import type { BadgeProps } from "@/shared/components/ui/badge";
import { warnUnexpectedType } from "@/shared/utils/common";
import { formatNumberDisplay } from "@/shared/utils/number";

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

export interface CommitLogEmptyState {
  title: string;
  message: string;
}

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
  if (!isRetrying) {
    return {
      title: "Commit log not available yet",
      message: "No worker has answered yet. Refresh to check again.",
    };
  }
  return {
    title: "Commit log not available yet",
    message: message || "Waiting for a worker to answer.",
  };
}

export function getNoCommitLogState({
  condition,
}: Pick<RepositoryCommitLog, "condition">): CommitLogEmptyState | null {
  switch (condition) {
    case RepositoryGitCondition.NOT_TRACKED:
      return { title: "No commit log", message: "This branch tracks no remote ref." };
    case RepositoryGitCondition.NO_REMOTE:
      return { title: "No commit log", message: "The tracked ref has no remote counterpart." };
    default:
      return null;
  }
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

export interface CommitStateContext extends Pick<RepositoryCommitLog, "condition"> {
  importedCommit: string | null;
  updatedOnlyByRebase: boolean;
}

export function getStateBadges(
  { hash, state }: Pick<RepositoryCommit, "hash" | "state">,
  { importedCommit, condition, updatedOnlyByRebase }: CommitStateContext
): CommitStateBadge[] {
  switch (state) {
    case RepositoryCommitState.HEAD:
      if (hash === importedCommit) return [REMOTE_HEAD_BADGE, IMPORTED_BADGE];
      // Only BEHIND guarantees the head is newer than the branch's commit; after a reset it can be an ancestor.
      return updatedOnlyByRebase && condition === RepositoryGitCondition.BEHIND
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

export interface CommitLogNotice {
  tone: "warning" | "neutral";
  message: string;
}

const getRefName = (gitRef: string | null) => gitRef ?? "the default branch";

export function getNonSyncedBranchNote({
  condition,
  git_ref,
  pending_count,
}: Pick<RepositoryCommitLog, "condition" | "git_ref" | "pending_count">): string | null {
  const ref = getRefName(git_ref);
  switch (condition) {
    case RepositoryGitCondition.BEHIND:
      if (pending_count === null) {
        return `This branch does not sync with Git and is behind ${ref}. Rebase the branch to use the newer commits.`;
      }
      return `This branch does not sync with Git and is behind ${ref} by ${formatCommitCount(pending_count)}. Rebase the branch to use ${pending_count === 1 ? "it" : "them"}.`;
    case RepositoryGitCondition.IN_SYNC:
      return `This branch does not sync with Git and is up to date with ${ref}.`;
    default:
      return null;
  }
}

export function getConditionNotice(
  {
    condition,
    git_ref,
    pending_count,
    imported_commit,
  }: Pick<RepositoryCommitLog, "condition" | "git_ref" | "pending_count" | "imported_commit">,
  { updatedOnlyByRebase }: Pick<CommitStateContext, "updatedOnlyByRebase">
): CommitLogNotice | null {
  switch (condition) {
    case RepositoryGitCondition.REWRITTEN:
      if (updatedOnlyByRebase) {
        const ref = getRefName(git_ref);
        const usedCommit = imported_commit ? ` (${imported_commit.slice(0, 7)})` : "";
        return {
          tone: "warning",
          message: `This branch does not sync with Git and has diverged from ${ref}: the commit it uses${usedCommit} is no longer in the history of ${ref}, for example after a force push. Rebase the branch to use the latest commit of ${ref}.`,
        };
      }
      return {
        tone: "warning",
        message:
          "The tracked ref was rewritten. The imported commit is no longer part of its history, so nothing is reported as pending.",
      };
    case RepositoryGitCondition.ORPHANED:
      return { tone: "warning", message: "The imported commit could not be found on the remote." };
    case RepositoryGitCondition.REF_MISSING:
      return {
        tone: "warning",
        message:
          "The tracked ref no longer exists on the remote. The imported commit is still the one in use.",
      };
    case RepositoryGitCondition.BEHIND:
      // On a branch updated only by rebase, the header line already gives the distance.
      return pending_count === null || updatedOnlyByRebase
        ? null
        : { tone: "neutral", message: `${formatCommitCount(pending_count)} pending import` };
    default:
      return null;
  }
}

const COMMITS_TAB_COUNT_CAP = 999;

export type CommitsTabSignal =
  | { kind: "pending-import" | "behind"; count: number; description: string; hint: string }
  | { kind: "warning"; description: string; hint: string };

export function formatCommitsTabCount(count: number): string {
  return count > COMMITS_TAB_COUNT_CAP ? `${COMMITS_TAB_COUNT_CAP}+` : `${count}`;
}

export function getCommitsTabSignal(
  {
    condition,
    git_ref,
    pending_count,
  }: Pick<RepositoryCommitLog, "condition" | "git_ref" | "pending_count">,
  {
    updatedOnlyByRebase,
    isReadOnly,
  }: Pick<CommitStateContext, "updatedOnlyByRebase"> & { isReadOnly: boolean }
): CommitsTabSignal | null {
  const ref = getRefName(git_ref);
  switch (condition) {
    case RepositoryGitCondition.BEHIND: {
      if (!pending_count) return null;
      const them = pending_count === 1 ? "it" : "them";
      if (updatedOnlyByRebase) {
        const description = `${formatCommitCount(pending_count)} behind ${ref}`;
        return {
          kind: "behind",
          count: pending_count,
          description,
          hint: `${description} — rebase the branch to use ${them}`,
        };
      }
      const description = `${formatCommitCount(pending_count)} pending import`;
      // Nothing imports a read-only repository on its own; its periodic check only notices that the ref moved.
      const action = isReadOnly
        ? `run Import latest commit to use ${them}`
        : `the next sync imports ${them}`;
      return {
        kind: "pending-import",
        count: pending_count,
        description,
        hint: `${description} — ${action}`,
      };
    }
    case RepositoryGitCondition.REWRITTEN:
      return updatedOnlyByRebase
        ? {
            kind: "warning",
            description: `diverged from ${ref}`,
            hint: `This branch has diverged from ${ref}. Rebase the branch to use the latest commit of ${ref}.`,
          }
        : {
            kind: "warning",
            description: "history rewritten",
            hint: "The remote branch history was rewritten, so nothing is reported as pending import.",
          };
    case RepositoryGitCondition.ORPHANED:
      return {
        kind: "warning",
        description: "imported commit missing",
        hint: "The imported commit could not be found on the remote.",
      };
    case RepositoryGitCondition.REF_MISSING:
      return {
        kind: "warning",
        description: "tracked ref missing",
        hint: "The tracked branch or tag no longer exists on the remote. The imported commit is still in use.",
      };
    default:
      return null;
  }
}

function formatCommitCount(count: number): string {
  return `${formatNumberDisplay(count)} ${count === 1 ? "commit" : "commits"}`;
}
