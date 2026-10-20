import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

export function useDefaultBranch() {
  const { data: branches } = useGetBranches();
  return branches?.find((branch) => branch.is_default);
}
