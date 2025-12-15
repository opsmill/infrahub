import { queryOptions, useQuery } from "@tanstack/react-query";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { getBranchesCount } from "@/entities/branches/domain/get-branches-count";

// Count query for branches list header badge
export function getBranchesCountQueryOptions(branchName?: string) {
  return queryOptions({
    queryKey: branchesQueryKeys.count(branchName),
    queryFn: () => getBranchesCount(branchName),
  });
}

export function useGetBranchesCount(branchName?: string) {
  return useQuery(getBranchesCountQueryOptions(branchName));
}
