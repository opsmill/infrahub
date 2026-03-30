import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { PaginationParams } from "@/shared/api/types";
import usePagination from "@/shared/hooks/usePagination";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectPermissionsParams,
  getObjectPermissions,
} from "@/entities/role-manager/domain/get-object-permissions";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";

export function getObjectPermissionsQueryOptions(params: GetObjectPermissionsParams) {
  return queryOptions({
    queryKey: roleManagerQueryKeys.objectPermissions(params),
    queryFn: () => getObjectPermissions(params),
    placeholderData: keepPreviousData,
  });
}

export function useGetObjectPermissions({
  search,
}: Omit<GetObjectPermissionsParams, keyof PaginationParams | "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();

  return useQuery(
    getObjectPermissionsQueryOptions({
      search,
      offset,
      limit,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
