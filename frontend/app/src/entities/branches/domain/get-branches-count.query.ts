import { queryOptions, useQuery } from "@tanstack/react-query";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { getBranchesCount } from "@/entities/branches/domain/get-branches-count";

// Count query for branches list header badge
export function getBranchesCountQueryOptions(branchSearch?: string) {
  return queryOptions({
    queryKey: branchesQueryKeys.count(branchSearch),
    queryFn: () => getBranchesCount(branchSearch),
  });
}

export function useGetBranchesCount(branchSearch?: string) {
  return useQuery(getBranchesCountQueryOptions(branchSearch));
}
