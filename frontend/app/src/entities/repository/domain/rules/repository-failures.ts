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

// Failing repositories past the list limits. A listed repository that also fails the other way is
// in that list's server total, so it is taken out of the remainder when it isn't listed there too.
// One past the limit of both lists can't be recognised from here, so it is still counted twice.
export function countUnlistedFailures(health: BranchRepositoryHealth | undefined): number {
  if (!health) return 0;

  const importErrorIds = new Set(health.importErrors.map(({ id }) => id));
  const unreachableIds = new Set(health.unreachable.map(({ id }) => id));
  const alsoUnreachable = health.importErrors.filter(
    (repository) => isRepositoryUnreachable(repository) && !unreachableIds.has(repository.id)
  ).length;
  const alsoImportError = health.unreachable.filter(
    (repository) => hasImportError(repository) && !importErrorIds.has(repository.id)
  ).length;

  return Math.max(
    0,
    health.importErrorCount -
      health.importErrors.length -
      alsoImportError +
      health.unreachableCount -
      health.unreachable.length -
      alsoUnreachable
  );
}

export function getBandKind(repository: BranchRepository): RepositoryBandKind {
  return hasImportError(repository) ? "import-error" : "unreachable";
}
