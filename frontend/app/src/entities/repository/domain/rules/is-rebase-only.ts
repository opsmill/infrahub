import {
  REPOSITORY_INTERNAL_STATUS_STAGING,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

// Mirrors the backend, which marks the default branch's newer commits as not on the branch when a rebase is the only way to bring them in.
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
