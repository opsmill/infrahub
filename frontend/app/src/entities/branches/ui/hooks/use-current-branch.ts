import { currentBranchAtom } from "@/entities/branches/stores";
import { useAtomValue } from "jotai";

export const useCurrentBranch = () => {
  return useAtomValue(currentBranchAtom);
};
