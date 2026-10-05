export const REPOSITORY_SYNC_REFETCH_INTERVAL_MS = 10_000;

// A repository can show the import error before its import run has ended as failed, so the lookup
// for that run is repeated a few times before the band settles on "not found".
export const MAX_IMPORT_TASK_LOOKUPS = 6;
