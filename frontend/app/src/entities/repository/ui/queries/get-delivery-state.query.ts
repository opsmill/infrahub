import { queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
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

// Only the default branch holds the live state; another branch holds an old copy.
export function useGetDeliveryState(
  params: Omit<GetDeliveryStateParams, keyof BranchContextParams>
) {
  const defaultBranch = useDefaultBranch();

  return useQuery({
    ...getDeliveryStateQueryOptions({ ...params, branchName: defaultBranch?.name ?? "" }),
    enabled: !!defaultBranch,
  });
}
