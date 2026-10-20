import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

// Mirrors the backend, which answers with the trunk's log for a read-write repository on a branch that does not sync with Git.
export function isShowingTrunkHistory({
  repositoryKind,
  branch,
}: {
  repositoryKind: string;
  branch: Pick<BranchListItem, "is_default" | "sync_with_git">;
}): boolean {
  return repositoryKind === REPOSITORY_KIND && !branch.is_default && branch.sync_with_git === false;
}
