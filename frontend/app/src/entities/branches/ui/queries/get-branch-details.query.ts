import { queryOptions, useQuery } from "@tanstack/react-query";

import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import {
  type GetBranchDetailsParams,
  getBranchDetails,
} from "@/entities/branches/domain/get-branch-details";

export function getBranchDetailsQueryOptions(params: GetBranchDetailsParams) {
  return queryOptions({
    queryKey: branchesQueryKeys.details(params),
    queryFn: () => getBranchDetails(params),
  });
}

export function useGetBranchDetails(params: GetBranchDetailsParams) {
  return useQuery(getBranchDetailsQueryOptions(params));
}
