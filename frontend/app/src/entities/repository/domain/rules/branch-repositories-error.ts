import { ERROR_CODES } from "@/shared/api/errors";
import { hasOnlyThrownCatalogueCode } from "@/shared/api/graphql/error-handling";

import { BranchRepositoriesError } from "@/entities/repository/domain/model/branch-repository";

// A missing object permission rejects the whole query rather than dropping rows from it.
export function toBranchRepositoriesError(error: unknown): BranchRepositoriesError {
  const code = hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)
    ? "PERMISSION_DENIED"
    : "UNKNOWN";
  const message = error instanceof Error ? error.message : "Failed to load the repositories";

  return new BranchRepositoriesError(code, message, { cause: error });
}

export function isRepositoryAccessDenied(error: unknown): boolean {
  return error instanceof BranchRepositoriesError && error.code === "PERMISSION_DENIED";
}
