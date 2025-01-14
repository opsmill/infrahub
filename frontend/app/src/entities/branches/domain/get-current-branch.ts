import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
import { store } from "@/shared/stores";

export const getCurrentBranchName = () => {
  const currentBranch = store.get(currentBranchAtom);
  return currentBranch?.name ?? DEFAULT_BRANCH_NAME;
};
