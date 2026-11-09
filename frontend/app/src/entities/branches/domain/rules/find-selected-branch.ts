import type { BranchListItem } from "@/entities/branches/domain/model/branch";

export const findSelectedBranch = (
  branches: BranchListItem[],
  branchName?: string | null
): BranchListItem | null => {
  const filter = branchName
    ? (b: BranchListItem) => branchName === b.name
    : (b: BranchListItem) => b.is_default;

  return branches.find(filter) ?? null;
};
