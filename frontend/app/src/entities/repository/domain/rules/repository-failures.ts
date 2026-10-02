import type {
  BranchRepository,
  BranchRepositoryHealth,
} from "@/entities/repository/domain/model/branch-repository";
import {
  REPOSITORY_OPERATIONAL_ERRORS,
  REPOSITORY_SYNC_STATUS_ERROR_VALUE,
} from "@/entities/repository/domain/model/repository";

export type RepositoryBandKind = "import-error" | "unreachable";

const OPERATIONAL_ERRORS: ReadonlySet<string> = new Set(REPOSITORY_OPERATIONAL_ERRORS);

export function hasImportError(repository: BranchRepository): boolean {
  return repository.syncStatus.value === REPOSITORY_SYNC_STATUS_ERROR_VALUE;
}

export function isRepositoryUnreachable(repository: BranchRepository): boolean {
  const { value } = repository.operationalStatus;
  return value !== null && OPERATIONAL_ERRORS.has(value);
}

// A repository both failing to import and unreachable is listed once, as an import error.
export function getFailingRepositories(
  health: BranchRepositoryHealth | undefined
): BranchRepository[] {
  if (!health) return [];

  const importErrorIds = new Set(health.importErrors.map(({ id }) => id));
  return [
    ...health.importErrors,
    ...health.unreachable.filter(({ id }) => !importErrorIds.has(id)),
  ];
}

// Failing repositories past the list limit. One that is both failing and unreachable, and past
// the limit of both lists, is counted twice.
export function countUnlistedFailures(health: BranchRepositoryHealth | undefined): number {
  if (!health) return 0;

  return (
    health.importErrorCount -
    health.importErrors.length +
    health.unreachableCount -
    health.unreachable.length
  );
}

export function getBandKind(repository: BranchRepository): RepositoryBandKind {
  return hasImportError(repository) ? "import-error" : "unreachable";
}
