import type { BranchGitRepository } from "@/entities/branch-git-status/domain/model/branch-git-repository";

export interface BranchGitSyncStatus {
  value: string | null;
  label: string | null;
  color: string | null;
  description: string | null;
}

export interface BranchRepositoryState {
  repository: BranchGitRepository;
  commit: string | null;
  syncStatus: BranchGitSyncStatus;
}

export interface SyncStatusCount {
  value: string | null;
  label: string;
  count: number;
}

export type FailedRepository =
  | { status: "denied"; repository: BranchGitRepository }
  | { status: "error"; repository: BranchGitRepository; message: string };

export type UnloadedRepository =
  | { status: "pending"; repository: BranchGitRepository }
  | FailedRepository;

// `repositories` is ordered worst first, and `counts` follows the same order.
export type BranchGitStatus =
  | { status: "pending" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | {
      status: "ok";
      repositories: BranchRepositoryState[];
      counts: SyncStatusCount[];
      unloaded: UnloadedRepository[];
    };

export type BranchGitStatusErrorCode = "PERMISSION_DENIED" | "UNKNOWN";

export class BranchGitStatusError extends Error {
  readonly code: BranchGitStatusErrorCode;

  constructor(code: BranchGitStatusErrorCode, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "BranchGitStatusError";
    this.code = code;
  }
}
