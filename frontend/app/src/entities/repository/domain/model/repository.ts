export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

export const REPOSITORY_SYNC_STATUS_ERROR_VALUE = "error-import";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

/**
 * Selects repositories whose import failed. Attribute-value filters match on substrings, so
 * this stays exact only while no other sync status value contains it.
 */
export const REPOSITORY_ERROR_IMPORT_FILTER = {
  name: `${REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME}__value`,
  value: REPOSITORY_SYNC_STATUS_ERROR_VALUE,
};
