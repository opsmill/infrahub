import type { RepositoryBranchStatusConnection } from "@/entities/branch-git-status/api/get-repository-branch-status-from-api";
import type { RepositoryBranchStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-status";
import type { BranchRepositorySyncStatus } from "@/entities/repository/domain/model/branch-repository";

type SyncStatusWire = RepositoryBranchStatusConnection["edges"][number]["node"]["sync_status"];

// A dropdown carrying no value is not a selection.
function toSyncStatus(syncStatus: SyncStatusWire): BranchRepositorySyncStatus | null {
  if (!syncStatus?.value) return null;
  return {
    value: syncStatus.value,
    label: syncStatus.label ?? null,
    color: syncStatus.color ?? null,
    description: syncStatus.description ?? null,
  };
}

export function toRepositoryBranchStatusPage(
  connection: RepositoryBranchStatusConnection
): RepositoryBranchStatusPage {
  return {
    rows: connection.edges.map(({ node }) => ({
      branchName: node.name.value,
      commit: node.commit?.value ?? null,
      syncStatus: toSyncStatus(node.sync_status),
    })),
    count: connection.count,
  };
}
