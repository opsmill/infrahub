import { queryOptions, useQuery } from "@tanstack/react-query";

import {
  type GetBranchActionStateParams,
  getBranchActionState,
} from "@/entities/branches/domain/get-branch-action-state";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";

export function getBranchActionStateQueryOptions(params: GetBranchActionStateParams) {
  return queryOptions({
    queryKey: branchesQueryKeys.actionState({
      branchName: params.branchName,
      workflow: params.workflow,
      state: params.state,
    }),
    queryFn: () => getBranchActionState(params),
  });
}

export function useGetBranchActionState(params: GetBranchActionStateParams) {
  return useQuery({
    ...getBranchActionStateQueryOptions(params),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
}
