import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { getMenu } from "@/shared/components/menu/domain/get-menu";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

export function menuQueryOptions({ branchName, atDate }: ContextParams) {
  return queryOptions({
    queryKey: [branchName, atDate, "menu"],
    queryFn: () => getMenu({ branchName, atDate }),
  });
}

export function useMenu(config?: QueryConfig<typeof menuQueryOptions>) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...menuQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    }),
    ...config,
  });
}
