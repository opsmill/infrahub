import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { REPOSITORY_SYNC_STATUS_UNKNOWN } from "@/entities/repository/domain/model/repository";
import type {
  RepositoryBranchStatusDropdown,
  RepositoryBranchStatusRow,
} from "@/entities/repository/domain/model/repository-branch-status";

export type { RepositoryBranchStatusDropdown, RepositoryBranchStatusRow };

export const UNKNOWN_SYNC_STATUS: RepositoryBranchStatusDropdown = {
  value: REPOSITORY_SYNC_STATUS_UNKNOWN,
  label: "Unknown",
  color: null,
  description: null,
};

export type CompareSyncStatusSeverity = (a: string | null, b: string | null) => number;

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

// `repositories` is ordered worst first.
export type BranchRepositorySummary =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | { status: "ok"; repositories: BranchRepositoryState[]; counts: SyncStatusCount[] };
