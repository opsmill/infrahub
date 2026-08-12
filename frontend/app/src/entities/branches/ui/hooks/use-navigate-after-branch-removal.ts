import type { NavigateFunction } from "react-router";
import { useNavigate } from "react-router";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

export function buildNavigateToPage(navigate: NavigateFunction) {
  return (listPath: string, deletedBranchName?: string) => {
    const currentBranch = getCurrentQsp().get(QSP.BRANCH);
    const path =
      deletedBranchName && currentBranch === deletedBranchName
        ? constructPath(listPath, [{ name: QSP.BRANCH, exclude: true }])
        : constructPath(listPath);

    navigate(path);
  };
}

export function buildClearBranchIfCurrent(navigate: NavigateFunction) {
  return (deletedBranchName?: string) => {
    const currentBranch = getCurrentQsp().get(QSP.BRANCH);
    if (deletedBranchName && currentBranch === deletedBranchName) {
      const path = constructPath(window.location.pathname, [{ name: QSP.BRANCH, exclude: true }]);
      navigate(path, { replace: true });
    }
  };
}

export function useNavigateAfterBranchRemoval() {
  const navigate = useNavigate();

  return {
    /** Navigate to a different page, stripping the branch QSP if the deleted branch was active. */
    navigateToPage: buildNavigateToPage(navigate),
    /** Clear the branch QSP on the current page if the deleted branch is the active one. No navigation. */
    clearBranchIfCurrent: buildClearBranchIfCurrent(navigate),
  };
}
