import { useAtomValue } from "jotai";

import { branchesState } from "@/entities/branches/stores";

export function useBranchExists(branchName?: string): boolean {
  const branches = useAtomValue(branchesState);
  if (!branchName) return false;
  return branches.some((b) => b.name === branchName);
}
