import type { RepositoryBranchStatusConnection } from "@/entities/branch-git-status/api/get-repository-branch-status-from-api";
import type { BranchGitSyncStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { RepositoryBranchGitStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-git-status";

type SyncStatusWire = RepositoryBranchStatusConnection["edges"][number]["node"]["sync_status"];

// A dropdown carrying no value is not a selection.
function toSyncStatus(syncStatus: SyncStatusWire): BranchGitSyncStatus | null {
  if (!syncStatus?.value) return null;
  return {
    value: syncStatus.value,
    label: syncStatus.label ?? null,
    color: syncStatus.color ?? null,
    description: syncStatus.description ?? null,
  };
}

export function toRepositoryBranchGitStatusPage(
  connection: RepositoryBranchStatusConnection
): RepositoryBranchGitStatusPage {
  return {
    rows: connection.edges.map(({ node }) => ({
      branchName: node.name.value,
      commit: node.commit?.value ?? null,
      syncStatus: toSyncStatus(node.sync_status),
    })),
    count: connection.count,
  };
}
