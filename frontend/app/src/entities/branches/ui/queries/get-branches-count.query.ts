import { queryOptions, useQuery } from "@tanstack/react-query";

import type { Filter } from "@/shared/hooks/useFilters";

import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import { getBranchesCount } from "@/entities/branches/domain/get-branches-count";

// Count query for branches list header badge
export function getBranchesCountQueryOptions(filters?: Filter[]) {
  return queryOptions({
    queryKey: branchesQueryKeys.count(filters),
    queryFn: () => getBranchesCount(filters),
  });
}

export function useGetBranchesCount(filters?: Filter[]) {
  return useQuery(getBranchesCountQueryOptions(filters));
}
