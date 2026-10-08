import type { BranchRepositorySyncStatus } from "@/entities/repository/domain/model/branch-repository";

export interface RepositoryBranchStatus {
  branchName: string;
  commit: string | null;
  syncStatus: BranchRepositorySyncStatus | null;
}

export interface RepositoryBranchStatusPage {
  rows: RepositoryBranchStatus[];
  count: number;
}
