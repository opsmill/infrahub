import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { PaginationParams } from "@/shared/api/types";
import usePagination from "@/shared/hooks/usePagination";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetGlobalPermissionsParams,
  getGlobalPermissions,
} from "@/entities/role-manager/domain/get-global-permissions";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";

export function getGlobalPermissionsQueryOptions(params: GetGlobalPermissionsParams) {
  return queryOptions({
    queryKey: roleManagerQueryKeys.globalPermissions(params),
    queryFn: () => getGlobalPermissions(params),
    placeholderData: keepPreviousData,
  });
}

export function useGetGlobalPermissions({
  search,
}: Omit<GetGlobalPermissionsParams, keyof PaginationParams | "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();

  return useQuery(
    getGlobalPermissionsQueryOptions({
      search,
      offset,
      limit,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
