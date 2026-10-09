import {
  type RepositoryCommit as GeneratedRepositoryCommit,
  RepositoryCommitState as GeneratedRepositoryCommitState,
  type RepositoryCommits as GeneratedRepositoryCommits,
  RepositoryGitCondition as GeneratedRepositoryGitCondition,
  type RepositoryGitUnavailable as GeneratedRepositoryGitUnavailable,
  RepositoryGitUnavailableReason as GeneratedRepositoryGitUnavailableReason,
} from "@/shared/api/graphql/generated/types";

import {
  TASK_STATE_CRASHED,
  TASK_STATE_FAILED,
  TASK_STATE_RUNNING,
} from "@/entities/tasks/domain/model/task";

export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

export const REPOSITORY_SYNC_STATUS_ERROR_VALUE = "error-import";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export const REPOSITORY_COMMITS_TAB = "repository_commits";

export const RepositoryCommitState = GeneratedRepositoryCommitState;
export type RepositoryCommitState = GeneratedRepositoryCommitState;

export const RepositoryGitCondition = GeneratedRepositoryGitCondition;
export type RepositoryGitCondition = GeneratedRepositoryGitCondition;

export const RepositoryGitUnavailableReason = GeneratedRepositoryGitUnavailableReason;
export type RepositoryGitUnavailableReason = GeneratedRepositoryGitUnavailableReason;

export type RepositoryGitUnavailable = Pick<
  GeneratedRepositoryGitUnavailable,
  "reason" | "message"
>;

export type RepositoryCommit = Pick<
  GeneratedRepositoryCommit,
  "hash" | "short_hash" | "summary" | "author_name" | "authored_at" | "state"
>;

export type RepositoryCommitLog = Pick<
  GeneratedRepositoryCommits,
  | "repository_id"
  | "branch_name"
  | "git_ref"
  | "condition"
  | "imported_commit"
  | "remote_head"
  | "pending_count"
  | "fetched_at"
  | "checked_at"
> & {
  unavailable: RepositoryGitUnavailable | null;
  commits: RepositoryCommit[];
};

export const REPOSITORY_SYNC_STATUS_SYNCING = "syncing";
export const REPOSITORY_SYNC_STATUS_IN_SYNC = "in-sync";
export const REPOSITORY_SYNC_STATUS_UNKNOWN = "unknown";
export const REPOSITORY_OPERATIONAL_ERRORS = ["error-cred", "error-connection", "error"] as const;

export const IMPORT_WORKFLOWS = [
  "git-repository-add-read-write",
  "git-repository-add-read-only",
  "git-repository-import-object",
  "git-read-only-repository-import-last-commit",
  "git-repository-pull-read-only",
  "sync-git-repo-with-origin",
] as const;
// A running import is included so an older failed run isn't shown while a newer one is still going.
export const IMPORT_TASK_STATES = [
  TASK_STATE_RUNNING,
  TASK_STATE_FAILED,
  TASK_STATE_CRASHED,
] as const;

/**
 * Selects repositories whose import failed. Attribute-value filters match on substrings, so
 * this stays exact only while no other sync status value contains it.
 */
export const REPOSITORY_ERROR_IMPORT_FILTER = {
  name: `${REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME}__value`,
  value: REPOSITORY_SYNC_STATUS_ERROR_VALUE,
};
