import type {
  GENERIC_REPOSITORY_KIND,
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

export type BranchRepositoryKind = typeof REPOSITORY_KIND | typeof READONLY_REPOSITORY_KIND;

export type BranchRepositoryListKind =
  | typeof GENERIC_REPOSITORY_KIND
  | typeof READONLY_REPOSITORY_KIND;

export interface BranchRepositorySyncStatus {
  value: string | null;
  label: string | null;
  color: string | null;
  description: string | null;
}

export interface BranchRepositoryOperationalStatus {
  value: string | null;
  label: string | null;
}

export interface BranchRepository {
  id: string;
  kind: BranchRepositoryKind;
  name: string;
  isReadOnly: boolean;
  commit: string | null;
  syncStatus: BranchRepositorySyncStatus;
  operationalStatus: BranchRepositoryOperationalStatus;
}

export interface BranchRepositoryPage {
  repositories: BranchRepository[];
  count: number;
}

// Each list stops at REPOSITORY_HEALTH_LIST_LIMIT; its count is the server's total.
export interface BranchRepositoryHealth {
  importErrors: BranchRepository[];
  importErrorCount: number;
  unreachable: BranchRepository[];
  unreachableCount: number;
  syncingCount: number;
}

export type BranchRepositoriesErrorCode = "PERMISSION_DENIED" | "UNKNOWN";

export class BranchRepositoriesError extends Error {
  readonly code: BranchRepositoriesErrorCode;

  constructor(code: BranchRepositoriesErrorCode, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "BranchRepositoriesError";
    this.code = code;
  }
}

export type RepositoryImportError =
  | { status: "found"; taskId: string; message: string }
  | { status: "not-found"; taskId: string | null };
