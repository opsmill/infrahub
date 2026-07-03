import { queryOptions, useQuery } from "@tanstack/react-query";

import { getBranchesCount } from "@/entities/branches/domain/use-cases/get-branches-count";
import { branchesQueryKeys } from "@/entities/branches/ui/queries/branch.query-keys";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

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
