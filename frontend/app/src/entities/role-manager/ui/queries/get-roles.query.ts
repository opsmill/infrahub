import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { PaginationParams } from "@/shared/api/types";
import usePagination from "@/shared/hooks/usePagination";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetRolesParams, getRoles } from "@/entities/role-manager/domain/get-roles";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";

export function getRolesQueryOptions(params: GetRolesParams) {
  return queryOptions({
    queryKey: roleManagerQueryKeys.roles(params),
    queryFn: () => getRoles(params),
    placeholderData: keepPreviousData,
  });
}

export function useGetRoles({
  search,
}: Omit<GetRolesParams, keyof PaginationParams | "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();

  return useQuery(
    getRolesQueryOptions({
      search,
      offset,
      limit,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
