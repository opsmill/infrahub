import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { store } from "@/state";
import { currentBranchAtom } from "@/state/atoms/branches.atom";

export const getCurrentBranchName = () => {
  const currentBranch = store.get(currentBranchAtom);
  return currentBranch?.name ?? DEFAULT_BRANCH_NAME;
};
