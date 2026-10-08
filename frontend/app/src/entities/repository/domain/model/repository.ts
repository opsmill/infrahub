import {
  type RepositoryCommit as GeneratedRepositoryCommit,
  RepositoryCommitState as GeneratedRepositoryCommitState,
  type RepositoryCommits as GeneratedRepositoryCommits,
  RepositoryGitCondition as GeneratedRepositoryGitCondition,
  type RepositoryGitUnavailable as GeneratedRepositoryGitUnavailable,
  RepositoryGitUnavailableReason as GeneratedRepositoryGitUnavailableReason,
} from "@/shared/api/graphql/generated/types";

export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export const REPOSITORY_COMMITS_TAB = "repository_commits";

export const READONLY_REPOSITORY_CHECK_REFS_WORKFLOW = "git-read-only-repository-check-refs";

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
