import { queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams, QueryConfig } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetNumberPoolForEditingParams,
  getNumberPoolForEditing,
} from "@/entities/resource-manager/domain/use-cases/get-number-pool-for-editing";
import { resourceManagerQueryKeys } from "@/entities/resource-manager/ui/queries/resource-manager.query-keys";

export function getNumberPoolForEditingQueryOptions(params: GetNumberPoolForEditingParams) {
  return queryOptions({
    queryKey: resourceManagerQueryKeys.numberPoolForEditing(params),
    queryFn: () => getNumberPoolForEditing(params),
  });
}

export function useGetNumberPoolForEditing(
  { poolId }: Omit<GetNumberPoolForEditingParams, keyof BranchContextParams>,
  config?: QueryConfig<typeof getNumberPoolForEditingQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getNumberPoolForEditingQueryOptions({ branchName: currentBranch.name, poolId }),
    ...config,
  });
}
