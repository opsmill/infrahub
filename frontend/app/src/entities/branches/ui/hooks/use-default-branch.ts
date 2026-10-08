import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

export function useDefaultBranch(): BranchListItem | undefined {
  const { data: branches } = useGetBranches();
  return branches?.find((branch) => branch.is_default);
}
