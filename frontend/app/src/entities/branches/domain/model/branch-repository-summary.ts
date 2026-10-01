import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import type { RepositoryBranchStatusDropdown } from "@/entities/repository/domain/model/repository-branch-status";

export type BranchRepositoryRef = Pick<BranchRepository, "id" | "name" | "kind" | "isReadOnly">;

export interface BranchRepositoryState {
  repository: BranchRepositoryRef;
  commit: string | null;
  syncStatus: RepositoryBranchStatusDropdown;
}

export interface SyncStatusCount {
  value: string | null;
  label: string;
  count: number;
}

// `repositories` is ordered worst first: repositories[0] drives the pill, the Git state and "+N more".
export type BranchRepositorySummary =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; repositories: BranchRepositoryState[]; counts: SyncStatusCount[] };
