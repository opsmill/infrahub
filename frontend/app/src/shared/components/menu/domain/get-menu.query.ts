import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
import { getMenu } from "@/shared/components/menu/domain/get-menu";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

export function menuQueryOptions({ branchName }: { branchName: string }) {
  return queryOptions({
    queryKey: [branchName, "menu"],
    queryFn: () => getMenu({ branchName }),
  });
}

export function useMenu() {
  const currentBranch = useAtomValue(currentBranchAtom);

  return useQuery(menuQueryOptions({ branchName: currentBranch?.name ?? DEFAULT_BRANCH_NAME }));
}
