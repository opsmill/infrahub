import {
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

// Follows the backend's choice of the default branch's history for a branch that receives no imports; its further checks only ever lead to an untracked log.
export function isRebaseOnly({
  repositoryKind,
  internalStatus,
  isDefaultBranch,
  syncWithGit,
}: {
  repositoryKind: string;
  internalStatus: string | null;
  isDefaultBranch: boolean | null | undefined;
  syncWithGit: boolean | null | undefined;
}): boolean {
  return (
    repositoryKind === REPOSITORY_KIND &&
    internalStatus !== REPOSITORY_INTERNAL_STATUS_STAGING &&
    !isDefaultBranch &&
    syncWithGit === false
  );
}
