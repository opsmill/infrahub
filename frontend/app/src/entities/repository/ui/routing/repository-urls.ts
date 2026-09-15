import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME,
  REPOSITORY_SYNC_STATUS_ERROR_VALUE,
} from "@/entities/repository/domain/model/repository";

/** Filters the repository list down to repositories whose import failed. */
export const REPOSITORY_ERROR_IMPORT_FILTER = {
  name: `${REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME}__value`,
  value: REPOSITORY_SYNC_STATUS_ERROR_VALUE,
};

/**
 * The repository list, scoped to a branch and filtered to failed imports.
 *
 * Takes the branch rather than a name because the default branch must be detected from
 * `is_default` — the default branch's name is deployment-configurable, so comparing against a
 * literal would silently break on any deployment that renamed it.
 */
export function getFailingRepositoriesUrl(currentBranch: BranchListItem): string {
  // The branch must come from context, not the URL: nuqs writes the query param one render
  // later, so a param inherited from the URL would still point at the previous branch.
  const branchParam: overrideQueryParams = currentBranch.is_default
    ? { name: QSP.BRANCH, exclude: true }
    : { name: QSP.BRANCH, value: currentBranch.name };

  return constructPath(`/objects/${GENERIC_REPOSITORY_KIND}`, [
    branchParam,
    { name: QSP.FILTER, value: JSON.stringify([REPOSITORY_ERROR_IMPORT_FILTER]) },
  ]);
}
