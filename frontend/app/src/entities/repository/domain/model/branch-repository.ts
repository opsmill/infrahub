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

export type BranchRepositoriesResult =
  | { status: "ok"; repositories: BranchRepository[]; count: number; isTruncated: boolean }
  | { status: "denied" };
