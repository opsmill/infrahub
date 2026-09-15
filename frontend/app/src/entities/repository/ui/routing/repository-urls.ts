import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_ERROR_IMPORT_FILTER,
} from "@/entities/repository/domain/model/repository";

/**
 * The repository list, scoped to a branch and filtered to failed imports.
 *
 * Takes the branch rather than a name because the default branch must be detected from
 * `is_default` — the default branch's name is deployment-configurable, so comparing against a
 * literal would silently break on any deployment that renamed it.
 */
export function getFailingRepositoriesUrl(currentBranch: BranchListItem): string {
  // Scoped from the branch passed in, never from whatever the URL currently says, so the
  // destination always matches the branch the caller is reporting on.
  const branchParam: overrideQueryParams = currentBranch.is_default
    ? { name: QSP.BRANCH, exclude: true }
    : { name: QSP.BRANCH, value: currentBranch.name };

  return constructPath(`/objects/${GENERIC_REPOSITORY_KIND}`, [
    branchParam,
    // The indicator reports current health, so its destination must be current too. Left
    // alone, an open time-frame selection is carried forward and the list shows the branch as
    // it was, which may not contain the repository that is failing now.
    { name: QSP.DATETIME, exclude: true },
    { name: QSP.FILTER, value: JSON.stringify([REPOSITORY_ERROR_IMPORT_FILTER]) },
  ]);
}
