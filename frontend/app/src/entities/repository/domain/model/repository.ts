export const REPOSITORY_OBJECTS_TAB = "repository_objects";
export const REPOSITORY_GROUP = "CoreRepositoryGroup";
export const REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME = "sync_status";

export const GENERIC_REPOSITORY_KIND = "CoreGenericRepository";
export const REPOSITORY_KIND = "CoreRepository";
export const READONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export const REPOSITORY_DELIVERY_ATTRIBUTE_NAMES: readonly string[] = [
  "delivery_status",
  "delivery_failure_cause",
  "delivery_error",
  "delivery_queue",
  "delivery_held_regeneration",
  "delivery_last_abandonment",
  "delivery_last_delivered_commit",
  "delivery_reverted",
  "delivery_progress",
];
