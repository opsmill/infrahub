import { useNavigate } from "react-router";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

export function useNavigateAfterBranchRemoval() {
  const navigate = useNavigate();

  return (listPath: string, deletedBranchName?: string) => {
    const currentBranch = getCurrentQsp().get(QSP.BRANCH);
    const path =
      deletedBranchName && currentBranch === deletedBranchName
        ? constructPath(listPath, [{ name: QSP.BRANCH, exclude: true }])
        : constructPath(listPath);

    navigate(path);
  };
}
