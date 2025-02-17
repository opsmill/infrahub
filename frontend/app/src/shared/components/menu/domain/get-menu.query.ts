import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
import { ContextParams } from "@/shared/api/types";
import { getMenu } from "@/shared/components/menu/domain/get-menu";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

export function menuQueryOptions({ branchName, atDate }: ContextParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "menu"],
    queryFn: () => getMenu({ branchName, atDate }),
  });
}

export function useMenu() {
  const currentBranch = useAtomValue(currentBranchAtom);
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    menuQueryOptions({
      branchName: currentBranch?.name ?? DEFAULT_BRANCH_NAME,
      atDate: timeMachineDate,
    })
  );
}
