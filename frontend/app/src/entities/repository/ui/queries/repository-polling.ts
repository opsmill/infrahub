export const REPOSITORY_SYNC_REFETCH_INTERVAL_MS = 10_000;
// A failed poll retries at this pace so the card recovers on its own without hammering the API.
export const REPOSITORY_ERROR_REFETCH_INTERVAL_MS = 60_000;
// A run reports a new phase or branch every few seconds, while an idle check only has to notice a
// run that something else started.
export const REPOSITORY_ACTIVITY_ACTIVE_REFETCH_INTERVAL_MS = 5000;
export const REPOSITORY_ACTIVITY_IDLE_REFETCH_INTERVAL_MS = 30_000;
