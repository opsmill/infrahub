import { ERROR_CODES } from "@/shared/api/errors";
import { hasOnlyThrownCatalogueCode } from "@/shared/api/graphql/error-handling";

import { RepositoryActivityError } from "@/entities/repository/domain/model/repository-activity";

// The query answers a denied repository and an unknown one alike, so both mean the viewer cannot see it.
export function toRepositoryActivityError(error: unknown): RepositoryActivityError {
  const noAccess =
    hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED) ||
    hasOnlyThrownCatalogueCode(error, ERROR_CODES.NODE_NOT_FOUND);
  const message = error instanceof Error ? error.message : "Failed to load the repository activity";

  return new RepositoryActivityError(noAccess ? "NO_ACCESS" : "UNKNOWN", message, { cause: error });
}

export function isRepositoryActivityAccessDenied(error: unknown): boolean {
  return error instanceof RepositoryActivityError && error.code === "NO_ACCESS";
}
