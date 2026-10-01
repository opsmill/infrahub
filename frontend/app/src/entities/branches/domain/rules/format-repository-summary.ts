import type {
  BranchRepositoryState,
  SyncStatusCount,
} from "@/entities/branches/domain/model/branch-repository-summary";

const SHORT_COMMIT_LENGTH = 7;

export function formatRepositoryState({ repository, commit, syncStatus }: BranchRepositoryState) {
  return [
    syncStatus.label || syncStatus.value,
    commit?.slice(0, SHORT_COMMIT_LENGTH),
    repository.isReadOnly && "read-only",
  ]
    .filter(Boolean)
    .join(" · ");
}

export function formatSyncStatusCounts(counts: readonly SyncStatusCount[]): string {
  return counts.map(({ label, count }) => `${label}: ${count}`).join(" · ");
}
