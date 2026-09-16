import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";

/** The repository list, scoped to a branch and filtered to failed imports. */
export function getFailingRepositoriesUrl(currentBranch: BranchListItem): string {
  const branchParam: overrideQueryParams = currentBranch.is_default
    ? { name: QSP.BRANCH, exclude: true }
    : { name: QSP.BRANCH, value: currentBranch.name };

  return constructPath(`/objects/${GENERIC_REPOSITORY_KIND}`, [
    branchParam,
    // Dropped so the destination shows current state, like the indicator itself.
    { name: QSP.DATETIME, exclude: true },
    { name: QSP.FILTER, value: JSON.stringify([REPOSITORY_ERROR_IMPORT_FILTER]) },
  ]);
}
