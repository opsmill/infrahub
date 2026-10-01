import type { BadgeProps } from "@/shared/components/ui/badge";
import { pluralize } from "@/shared/utils/string";

import {
  type RepositoryCommit,
  type RepositoryCommitLog,
  RepositoryCommitState,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";

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

export interface CommitLogEmptyState {
  title: string;
  message: string;
}

export function getEmptyState({
  condition,
  unavailable,
}: Pick<RepositoryCommitLog, "condition" | "unavailable">): CommitLogEmptyState | null {
  switch (condition) {
    case RepositoryGitCondition.UNAVAILABLE:
      return {
        title: "Commit log not available yet",
        message: unavailable?.message ?? "Waiting for a worker to answer.",
      };
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
    // A check that brought the update already shows that time.
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
