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

export const REPOSITORY_SYNC_STATUS_SYNCING = "syncing";
export const REPOSITORY_OPERATIONAL_ERRORS = ["error-cred", "error-connection", "error"] as const;

export const IMPORT_WORKFLOWS = [
  "git-repository-add-read-write",
  "git-repository-add-read-only",
  "git-repository-import-object",
  "git-read-only-repository-import-last-commit",
  "git-repository-pull-read-only",
  "sync-git-repo-with-origin",
] as const;
export const IMPORT_FAILED_TASK_STATES = [TASK_STATE_FAILED, TASK_STATE_CRASHED] as const;
export const IMPORT_ACTIVE_TASK_STATES = [TASK_STATE_RUNNING] as const;
// Logs come back oldest first, so anything below the backend's 10 000-line cap can cut off the final error line.
export const IMPORT_LOG_LIMIT = 10_000;

export const MAX_VISIBLE_BANDS = 3;
export const REPOSITORY_HEALTH_LIST_LIMIT = 50;

/**
 * Selects repositories whose import failed. Attribute-value filters match on substrings, so
 * this stays exact only while no other sync status value contains it.
 */
export const REPOSITORY_ERROR_IMPORT_FILTER = {
  name: `${REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME}__value`,
  value: REPOSITORY_SYNC_STATUS_ERROR_VALUE,
};
