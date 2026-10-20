import type { BranchGitStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";

export interface BranchTableRow extends BranchListItem {
  gitStatus: BranchGitStatus;
}

const PENDING_GIT_STATUS: BranchGitStatus = { status: "pending" };

export function toBranchTableRows(
  branches: readonly BranchListItem[],
  gitStatusesByBranchName: Record<string, BranchGitStatus>
): BranchTableRow[] {
  return branches.map((branch) => ({
    ...branch,
    gitStatus: gitStatusesByBranchName[branch.name] ?? PENDING_GIT_STATUS,
  }));
}
