import { queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import {
  type GetDeliveryStateParams,
  getDeliveryState,
} from "@/entities/repository/domain/use-cases/get-delivery-state";

function getDeliveryStateQueryOptions(params: GetDeliveryStateParams) {
  return queryOptions({
    queryKey: [
      ...objectQueryKeys.lists({
        branchName: params.branchName,
        atDate: null,
        objectKind: REPOSITORY_KIND,
      }),
      params.repositoryId,
      "delivery-state",
    ],
    queryFn: () => getDeliveryState(params),
  });
}

// Only the default branch holds the live state; any other branch holds a stale copy from its fork.
export function useGetDeliveryState(
  params: Omit<GetDeliveryStateParams, keyof BranchContextParams>
) {
  const { data: branches } = useGetBranches();
  const defaultBranch = branches?.find((branch) => branch.is_default);

  return useQuery({
    ...getDeliveryStateQueryOptions({ ...params, branchName: defaultBranch?.name ?? "" }),
    enabled: !!defaultBranch,
  });
}
