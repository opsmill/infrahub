import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

// Mirrors the backend, which lists the trunk with its newer commits marked as not on the branch in exactly this case.
export function isUpdatedOnlyByRebase({
  repositoryKind,
  internalStatus,
  branch,
}: {
  repositoryKind: string;
  internalStatus: string | null;
  branch: Pick<BranchListItem, "is_default" | "sync_with_git">;
}): boolean {
  return (
    repositoryKind === REPOSITORY_KIND &&
    internalStatus !== REPOSITORY_INTERNAL_STATUS_STAGING &&
    !branch.is_default &&
    branch.sync_with_git === false
  );
}
