export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

/**
 * The one sync status that means a repository is broken. Mirrors the backend's
 * `RepositorySyncStatus.ERROR_IMPORT`; keep the two in step.
 *
 * Filters on `<attribute>__value` are submitted as partial matches, so this being an exact
 * match today depends on no other sync status containing it as a substring. That holds for the
 * current set (unknown, in-sync, error-import, syncing) but is not enforced — if a value were
 * ever added that contained this one, counts filtered on it would silently inflate.
 */
export const REPOSITORY_SYNC_STATUS_ERROR_VALUE = "error-import";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

/**
 * Selects repositories whose import failed. Lives here rather than beside the URL builder
 * because it is domain vocabulary — it is used both to filter the repository list and to scope
 * a count query, and only one of those is routing.
 */
export const REPOSITORY_ERROR_IMPORT_FILTER = {
  name: `${REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME}__value`,
  value: REPOSITORY_SYNC_STATUS_ERROR_VALUE,
};
