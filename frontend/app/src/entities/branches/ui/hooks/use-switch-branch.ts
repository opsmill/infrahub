import { useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

export function useSwitchBranch() {
  const { currentBranch, setCurrentBranch } = useCurrentBranch();
  const [, setBranchInQueryString] = useQueryState(QSP.BRANCH);

  function switchBranch(branch: BranchListItem) {
    // The default branch is represented by an absent query string, not by its name.
    setBranchInQueryString(branch.is_default ? null : branch.name);
    setCurrentBranch(branch);
  }

  return { currentBranch, switchBranch };
}
