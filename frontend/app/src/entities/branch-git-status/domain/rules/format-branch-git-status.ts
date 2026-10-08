import type {
  BranchRepositoryState,
  FailedRepository,
  SyncStatusCount,
} from "@/entities/branch-git-status/domain/model/branch-git-status";

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

export function formatFailedRepositoryCount(count: number): string {
  return `${count} ${count === 1 ? "repository" : "repositories"} could not be loaded`;
}

export function formatFailedRepositoryReasons(failed: readonly FailedRepository[]): string {
  return failed
    .map((failure) => {
      const reason = failure.status === "error" ? failure.message : "No permission";
      return `${failure.repository.name}: ${reason}`;
    })
    .join(" · ");
}
