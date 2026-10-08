import { ERROR_CODES } from "@/shared/api/errors";
import { hasOnlyThrownCatalogueCode } from "@/shared/api/graphql/error-handling";

import { BranchGitStatusError } from "@/entities/branch-git-status/domain/model/branch-git-status";

// A missing object permission rejects the whole query rather than dropping rows from it.
export function toBranchGitStatusError(
  error: unknown,
  fallbackMessage: string
): BranchGitStatusError {
  const code = hasOnlyThrownCatalogueCode(error, ERROR_CODES.PERMISSION_DENIED)
    ? "PERMISSION_DENIED"
    : "UNKNOWN";
  const message = error instanceof Error ? error.message : fallbackMessage;

  return new BranchGitStatusError(code, message, { cause: error });
}

export function isBranchGitStatusAccessDenied(error: unknown): boolean {
  return error instanceof BranchGitStatusError && error.code === "PERMISSION_DENIED";
}
