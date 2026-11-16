import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { isRebaseOnly } from "@/entities/repository/domain/rules/is-rebase-only";

export function useIsRebaseOnly({
  repositoryKind,
  internalStatus,
}: {
  repositoryKind: string;
  internalStatus: string | null;
}): boolean {
  const { currentBranch } = useCurrentBranch();

  return isRebaseOnly({
    repositoryKind,
    internalStatus,
    isDefaultBranch: currentBranch.is_default,
    syncWithGit: currentBranch.sync_with_git,
  });
}
