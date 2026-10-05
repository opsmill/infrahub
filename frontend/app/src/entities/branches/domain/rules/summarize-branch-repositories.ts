import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoryRef,
  BranchRepositoryState,
  BranchRepositorySummary,
  CompareSyncStatusSeverity,
  RepositoryBranchStatusDropdown,
  RepositoryBranchStatusRow,
  SyncStatusCount,
} from "@/entities/branches/domain/model/branch-repository-summary";

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
  // Permission is checked per repository kind, so one denied kind only hides its own repositories.
  if (fetches.length > 0 && fetches.every(({ status }) => status === "denied")) {
    return { status: "denied" };
  }
  if (fetches.some(({ status }) => status === "pending")) return { status: "pending" };

  const error = fetches.find((fetch) => fetch.status === "error");
  if (error) return error;

  return null;
}

function compareStates(
  compareSeverity: CompareSyncStatusSeverity,
  a: BranchRepositoryState,
  b: BranchRepositoryState
): number {
  return (
    compareSeverity(a.syncStatus.value, b.syncStatus.value) ||
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
  fetches: readonly RepositoryStatusFetch[],
  compareSeverity: CompareSyncStatusSeverity
): Record<string, BranchRepositorySummary> {
  const shared = getSharedSummary(fetches);
  if (shared) return Object.fromEntries(branches.map((branch) => [branch.name, shared]));

  const loaded = fetches.filter((fetch): fetch is LoadedFetch => fetch.status === "ok");
  const statesByBranch = groupStatesByBranch(loaded);
  const truncated = loaded.filter(({ rows, count }) => count > rows.length);

  return Object.fromEntries(
    branches.map((branch) => {
      const states = statesByBranch.get(branch.name) ?? [];
      // Which branches a repository lists is the backend's rule, so a branch missing from a cut page is
      // reported as unknown rather than guessed absent.
      const cutBefore = truncated.filter(
        ({ rows }) => !rows.some((row) => row.name === branch.name)
      );
      if (cutBefore.length > 0) return [branch.name, truncatedSummary(cutBefore)];
      const repositories = [...states].sort((a, b) => compareStates(compareSeverity, a, b));
      return [branch.name, { status: "ok", repositories, counts: countBySyncStatus(repositories) }];
    })
  );
}

function truncatedSummary(cutBefore: readonly LoadedFetch[]): BranchRepositorySummary {
  const names = cutBefore.map(({ repository }) => repository.name).join(", ");
  return {
    status: "error",
    message: `The status list for ${names} was cut short before this branch. Open the branch for the full list.`,
  };
}
