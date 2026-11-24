import type { RepositoryBranchStatusDropdown } from "@/entities/repository/domain/model/repository-branch-status";

export function SyncStatusCell({ syncStatus }: { syncStatus: RepositoryBranchStatusDropdown }) {
  return (
    <span
      className="truncate rounded-full px-2.5 py-1"
      style={
        syncStatus.color
          ? {
              backgroundColor: syncStatus.color,
              color: `lch(from ${syncStatus.color} calc((50 - l) * 999) 0 0)`, // https://x.com/devongovett/status/1863733091409461256
            }
          : undefined
      }
    >
      {syncStatus.label ?? syncStatus.value}
    </span>
  );
}
