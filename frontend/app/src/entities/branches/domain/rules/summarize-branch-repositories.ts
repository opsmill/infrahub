import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoryRef,
  BranchRepositoryState,
  BranchRepositorySummary,
  SyncStatusCount,
} from "@/entities/branches/domain/model/branch-repository-summary";
import type {
  RepositoryBranchStatusDropdown,
  RepositoryBranchStatusRow,
} from "@/entities/repository/domain/model/repository-branch-status";
import { compareSyncStatusSeverity } from "@/entities/repository/domain/rules/sync-status-severity";

export type RepositoryStatusFetch =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | {
      status: "ok";
      repository: BranchRepositoryRef;
      rows: RepositoryBranchStatusRow[];
      count: number;
    };

type LoadedFetch = Extract<RepositoryStatusFetch, { status: "ok" }>;

const NO_SYNC_STATUS: RepositoryBranchStatusDropdown = {
  value: null,
  label: null,
  color: null,
  description: null,
};

function getSharedSummary(
  fetches: readonly RepositoryStatusFetch[]
): BranchRepositorySummary | null {
  if (fetches.some(({ status }) => status === "denied")) return { status: "denied" };
  if (fetches.some(({ status }) => status === "pending")) return { status: "pending" };

  const error = fetches.find((fetch) => fetch.status === "error");
  if (error) return error;

  return null;
}

function compareStates(a: BranchRepositoryState, b: BranchRepositoryState): number {
  return (
    compareSyncStatusSeverity(a.syncStatus.value, b.syncStatus.value) ||
    a.repository.name.localeCompare(b.repository.name, undefined, { sensitivity: "base" })
  );
}

function groupStatesByBranch(fetches: readonly LoadedFetch[]) {
  const statesByBranch = new Map<string, BranchRepositoryState[]>();

  for (const { repository, rows } of fetches) {
    for (const row of rows) {
      const state = {
        repository,
        commit: row.commit,
        syncStatus: row.syncStatus ?? NO_SYNC_STATUS,
      };
      const states = statesByBranch.get(row.name);
      if (states) states.push(state);
      else statesByBranch.set(row.name, [state]);
    }
  }

  return statesByBranch;
}

function countBySyncStatus(states: readonly BranchRepositoryState[]): SyncStatusCount[] {
  const counts = new Map<string | null, SyncStatusCount>();

  for (const { syncStatus } of states) {
    const value = syncStatus.value ?? null;
    const entry = counts.get(value);
    if (entry) entry.count += 1;
    else counts.set(value, { value, label: syncStatus.label || value || "Unknown", count: 1 });
  }

  return [...counts.values()];
}

export function summarizeBranchRepositories(
  branches: readonly BranchListItem[],
  fetches: readonly RepositoryStatusFetch[]
): Record<string, BranchRepositorySummary> {
  const shared = getSharedSummary(fetches);
  if (shared) return Object.fromEntries(branches.map((branch) => [branch.name, shared]));

  const loaded = fetches.filter((fetch): fetch is LoadedFetch => fetch.status === "ok");
  const statesByBranch = groupStatesByBranch(loaded);
  const truncated = loaded.filter(({ rows, count }) => count > rows.length);

  return Object.fromEntries(
    branches.map((branch) => {
      const states = statesByBranch.get(branch.name) ?? [];
      // A branch absent from a page the backend cut short may still have rows past the cut.
      if (truncated.some(({ rows }) => !rows.some((row) => row.name === branch.name))) {
        return [branch.name, truncatedSummary(truncated, states.length)];
      }
      const repositories = [...states].sort(compareStates);
      return [branch.name, { status: "ok", repositories, counts: countBySyncStatus(repositories) }];
    })
  );
}

function truncatedSummary(
  truncated: readonly LoadedFetch[],
  known: number
): BranchRepositorySummary {
  const names = truncated.map(({ repository }) => repository.name).join(", ");
  return {
    status: "error",
    message: `Status for ${names} covers only the first ${truncated[0]?.rows.length ?? 0} branches; ${known} repositories known for this branch. Open the branch for the full list.`,
  };
}
