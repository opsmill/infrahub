import type { BadgeProps } from "@/shared/components/ui/badge";
import { warnUnexpectedType } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

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

export function getStateBadges(
  { hash, state }: Pick<RepositoryCommit, "hash" | "state">,
  importedCommit: string | null
): CommitStateBadge[] {
  switch (state) {
    case RepositoryCommitState.HEAD:
      return hash === importedCommit ? [REMOTE_HEAD_BADGE, IMPORTED_BADGE] : [REMOTE_HEAD_BADGE];
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

export function getConditionNotice({
  condition,
  pending_count,
}: Pick<RepositoryCommitLog, "condition" | "pending_count">): CommitLogNotice | null {
  switch (condition) {
    case RepositoryGitCondition.REWRITTEN:
      return {
        tone: "warning",
        message:
          "The tracked ref was rewritten. The imported commit is no longer part of its history, so nothing is reported as pending.",
      };
    case RepositoryGitCondition.ORPHANED:
      return { tone: "warning", message: "The imported commit could not be found on the remote." };
    case RepositoryGitCondition.BEHIND:
      return pending_count === null
        ? null
        : { tone: "neutral", message: `${pluralize(pending_count, "commit")} pending import` };
    default:
      return null;
  }
}
