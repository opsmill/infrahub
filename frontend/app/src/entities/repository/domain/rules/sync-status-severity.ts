import {
  REPOSITORY_SYNC_STATUS_IMPORT_ERROR,
  REPOSITORY_SYNC_STATUS_IN_SYNC,
  REPOSITORY_SYNC_STATUS_SYNCING,
} from "@/entities/repository/domain/model/repository";

type SyncStatusValue = string | null | undefined;

const UNKNOWN_SEVERITY = 2;

const SEVERITY = new Map<string, number>([
  [REPOSITORY_SYNC_STATUS_IMPORT_ERROR, 3],
  [REPOSITORY_SYNC_STATUS_SYNCING, 1],
  [REPOSITORY_SYNC_STATUS_IN_SYNC, 0],
]);

function getSyncStatusSeverity(value: SyncStatusValue): number {
  if (!value) return UNKNOWN_SEVERITY;
  return SEVERITY.get(value) ?? UNKNOWN_SEVERITY;
}

export function compareSyncStatusSeverity(a: SyncStatusValue, b: SyncStatusValue): number {
  return getSyncStatusSeverity(b) - getSyncStatusSeverity(a);
}
