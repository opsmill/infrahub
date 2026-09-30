export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export const REPOSITORY_COMMITS_TAB = "repository_commits";

export const REPOSITORY_COMMIT_STATE = {
  HEAD: "HEAD",
  IMPORTED: "IMPORTED",
  PENDING: "PENDING",
  HISTORY: "HISTORY",
  UNRELATED: "UNRELATED",
} as const;

export type RepositoryCommitState =
  (typeof REPOSITORY_COMMIT_STATE)[keyof typeof REPOSITORY_COMMIT_STATE];

export const REPOSITORY_GIT_CONDITION = {
  IN_SYNC: "IN_SYNC",
  BEHIND: "BEHIND",
  REWRITTEN: "REWRITTEN",
  ORPHANED: "ORPHANED",
  NO_REMOTE: "NO_REMOTE",
  NOT_TRACKED: "NOT_TRACKED",
  UNAVAILABLE: "UNAVAILABLE",
} as const;

export type RepositoryGitCondition =
  (typeof REPOSITORY_GIT_CONDITION)[keyof typeof REPOSITORY_GIT_CONDITION];

export const REPOSITORY_GIT_UNAVAILABLE_REASON = {
  NOT_CLONED: "NOT_CLONED",
  NOT_IMPLEMENTED: "NOT_IMPLEMENTED",
  TIMEOUT: "TIMEOUT",
} as const;

export type RepositoryGitUnavailableReason =
  (typeof REPOSITORY_GIT_UNAVAILABLE_REASON)[keyof typeof REPOSITORY_GIT_UNAVAILABLE_REASON];

export interface RepositoryGitUnavailable {
  reason: RepositoryGitUnavailableReason;
  message: string;
}

export interface RepositoryCommit {
  id: string;
  __typename: "RepositoryCommit";
  hash: string;
  shortHash: string;
  summary: string;
  authorName: string;
  authoredAt: string;
  state: RepositoryCommitState;
}

export interface RepositoryCommitLog {
  repositoryId: string;
  branchName: string;
  gitRef: string | null;
  condition: RepositoryGitCondition;
  importedCommit: string | null;
  remoteHead: string | null;
  pendingCount: number | null;
  fetchedAt: string | null;
  checkedAt: string | null;
  unavailable: RepositoryGitUnavailable | null;
  commits: RepositoryCommit[];
}
