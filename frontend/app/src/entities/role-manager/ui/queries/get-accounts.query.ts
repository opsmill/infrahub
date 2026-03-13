import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { PaginationParams } from "@/shared/api/types";
import usePagination from "@/shared/hooks/usePagination";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetAccountsParams, getAccounts } from "@/entities/role-manager/domain/get-accounts";
import { roleManagerQueryKeys } from "@/entities/role-manager/ui/queries/role-manager.query-keys";

export function getAccountsQueryOptions(params: GetAccountsParams) {
  return queryOptions({
    queryKey: roleManagerQueryKeys.accounts(params),
    queryFn: () => getAccounts(params),
    placeholderData: keepPreviousData,
  });
}

export function useGetAccounts({
  search,
}: Omit<GetAccountsParams, keyof PaginationParams | "branchName" | "atDate">) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const [{ offset, limit }] = usePagination();

  return useQuery(
    getAccountsQueryOptions({
      search,
      offset,
      limit,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
}
