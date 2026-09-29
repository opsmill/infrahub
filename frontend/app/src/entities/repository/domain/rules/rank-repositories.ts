import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import {
  REPOSITORY_OPERATIONAL_ERRORS,
  REPOSITORY_SYNC_STATUS_IMPORT_ERROR,
} from "@/entities/repository/domain/model/repository";

export type RepositoryBandKind = "import-error" | "unreachable";

const OPERATIONAL_ERRORS: ReadonlySet<string> = new Set(REPOSITORY_OPERATIONAL_ERRORS);

export function hasImportError(repository: BranchRepository): boolean {
  return repository.syncStatus.value === REPOSITORY_SYNC_STATUS_IMPORT_ERROR;
}

export function isRepositoryUnreachable(repository: BranchRepository): boolean {
  const { value } = repository.operationalStatus;
  return value !== null && OPERATIONAL_ERRORS.has(value);
}

export function getRepositoryRank(repository: BranchRepository): 2 | 1 | 0 {
  if (hasImportError(repository)) return 2;
  if (isRepositoryUnreachable(repository)) return 1;
  return 0;
}

export function rankRepositories(repositories: BranchRepository[]): BranchRepository[] {
  return [...repositories].sort(
    (a, b) =>
      getRepositoryRank(b) - getRepositoryRank(a) ||
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" })
  );
}

export function getFailingRepositories(repositories: BranchRepository[]): BranchRepository[] {
  return rankRepositories(repositories).filter((repository) => getRepositoryRank(repository) > 0);
}

export function getBandKind(repository: BranchRepository): RepositoryBandKind {
  return hasImportError(repository) ? "import-error" : "unreachable";
}
