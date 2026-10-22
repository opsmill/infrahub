import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

// Mirrors the backend, which marks the default branch's newer commits as not on the branch when a rebase is the only way to bring them in.
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
