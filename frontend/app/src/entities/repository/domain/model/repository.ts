export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export const REPOSITORY_SYNC_STATUS_IMPORT_ERROR = "error-import";
export const REPOSITORY_SYNC_STATUS_SYNCING = "syncing";
export const REPOSITORY_OPERATIONAL_ERRORS = ["error-cred", "error-connection", "error"] as const;
export const REPOSITORY_FETCH_LIMIT = 500;

export const IMPORT_WORKFLOWS = [
  "git-repository-add-read-write",
  "git-repository-add-read-only",
  "git-repository-import-object",
  "git-read-only-repository-import-last-commit",
  "git-repository-pull-read-only",
  "sync-git-repo-with-origin",
] as const;
// Logs come back oldest first, so anything below the backend's 10 000-line cap can cut off the final error line.
export const IMPORT_LOG_LIMIT = 10_000;

export const MAX_VISIBLE_BANDS = 3;
