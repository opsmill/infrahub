import type { BranchGitSyncStatus } from "@/entities/branch-git-status/domain/model/branch-git-status";

export interface RepositoryBranchGitStatus {
  branchName: string;
  commit: string | null;
  syncStatus: BranchGitSyncStatus | null;
}

export interface RepositoryBranchGitStatusPage {
  rows: RepositoryBranchGitStatus[];
  count: number;
}
