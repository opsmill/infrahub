import type { BranchGitRepository } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import type {
  BranchGitStatus,
  BranchGitSyncStatus,
  BranchRepositoryState,
  SyncStatusCount,
  UnloadedRepository,
} from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { RepositoryBranchGitStatus } from "@/entities/branch-git-status/domain/model/repository-branch-git-status";
import { compareWorstSyncStatusFirst } from "@/entities/branch-git-status/domain/rules/sync-status-severity";

interface LoadedRepositoryStatus {
  status: "ok";
  repository: BranchGitRepository;
  rows: RepositoryBranchGitStatus[];
  count: number;
}

export type RepositoryStatusFetch = LoadedRepositoryStatus | UnloadedRepository;

export type RepositoryListFetch =
  | Exclude<BranchGitStatus, { status: "ok" }>
  | { status: "ok"; statuses: readonly RepositoryStatusFetch[] };

function compareStates(a: BranchRepositoryState, b: BranchRepositoryState): number {
  return (
    compareWorstSyncStatusFirst(a.syncStatus.value, b.syncStatus.value) ||
    a.repository.name.localeCompare(b.repository.name, undefined, { sensitivity: "base" })
  );
}

function groupStatesByBranch(
  statuses: readonly LoadedRepositoryStatus[],
  unknownSyncStatus: BranchGitSyncStatus
) {
  const statesByBranch = new Map<string, BranchRepositoryState[]>();

  for (const { repository, rows } of statuses) {
    for (const row of rows) {
      const state = {
        repository,
        commit: row.commit,
        syncStatus: row.syncStatus ?? unknownSyncStatus,
      };
      const states = statesByBranch.get(row.branchName);
      if (states) states.push(state);
      else statesByBranch.set(row.branchName, [state]);
    }
  }

  return statesByBranch;
}

function countBySyncStatus(states: readonly BranchRepositoryState[]): SyncStatusCount[] {
  const counts = new Map<string | null, SyncStatusCount>();

  for (const { syncStatus } of states) {
    const { value } = syncStatus;
    const entry = counts.get(value);
    if (entry) entry.count += 1;
    else counts.set(value, { value, label: syncStatus.label || value || "", count: 1 });
  }

  return [...counts.values()];
}

function getTruncatedStatus(missingFrom: readonly LoadedRepositoryStatus[]): BranchGitStatus {
  const names = missingFrom.map(({ repository }) => repository.name).join(", ");
  return {
    status: "error",
    message: `Too many branches to load for ${names}, so this branch could not be checked. Open the branch for the full list.`,
  };
}

function summarizeBranch(
  branchName: string,
  loaded: readonly LoadedRepositoryStatus[],
  statesByBranch: Map<string, BranchRepositoryState[]>,
  unloaded: UnloadedRepository[]
): BranchGitStatus {
  // Which branches a repository lists is the backend's rule, so a branch missing from a cut page is
  // reported as an error rather than guessed absent.
  const missingFrom = loaded.filter(
    ({ rows, count }) => count > rows.length && !rows.some((row) => row.branchName === branchName)
  );
  if (missingFrom.length > 0) return getTruncatedStatus(missingFrom);

  const repositories = [...(statesByBranch.get(branchName) ?? [])].sort(compareStates);
  return { status: "ok", repositories, counts: countBySyncStatus(repositories), unloaded };
}

export function summarizeBranchGitStatuses(
  branchNames: readonly string[],
  repositoryList: RepositoryListFetch,
  unknownSyncStatus: BranchGitSyncStatus
): Record<string, BranchGitStatus> {
  const forEveryBranch = (status: BranchGitStatus) =>
    Object.fromEntries(branchNames.map((branchName) => [branchName, status]));

  if (repositoryList.status !== "ok") return forEveryBranch(repositoryList);

  const { statuses } = repositoryList;
  // Status reads are checked per repository, so the column reads as denied only when every read is.
  if (statuses.length > 0 && statuses.every(({ status }) => status === "denied")) {
    return forEveryBranch({ status: "denied" });
  }

  const loaded = statuses.filter(
    (status): status is LoadedRepositoryStatus => status.status === "ok"
  );
  const unloaded = statuses.filter(
    (status): status is UnloadedRepository => status.status !== "ok"
  );
  const statesByBranch = groupStatesByBranch(loaded, unknownSyncStatus);

  return Object.fromEntries(
    branchNames.map((branchName) => [
      branchName,
      summarizeBranch(branchName, loaded, statesByBranch, unloaded),
    ])
  );
}
