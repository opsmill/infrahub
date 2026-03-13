import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { PaginationParams } from "@/shared/api/types";
import usePagination from "@/shared/hooks/usePagination";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRoleManagerGroupsParams,
  getRoleManagerGroups,
} from "@/entities/role-manager/domain/get-groups";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";

export function getRoleManagerGroupsQueryOptions(params: GetRoleManagerGroupsParams) {
  return queryOptions({
    queryKey: roleManagerQueryKeys.groups(params),
    queryFn: () => getRoleManagerGroups(params),
    placeholderData: keepPreviousData,
  });
}

export function useGetRoleManagerGroups({
  search,
}: Omit<GetRoleManagerGroupsParams, keyof PaginationParams | "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();

  return useQuery(
    getRoleManagerGroupsQueryOptions({
      search,
      offset,
      limit,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
