import { queryOptions, useQuery } from "@tanstack/react-query";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { getBranches } from "@/entities/branches/domain/get-branches";

export function getBranchesQueryOptions() {
  return queryOptions({
    queryKey: branchesQueryKeys.all,
    queryFn: getBranches,
  });
}

export function useGetBranches() {
  return useQuery(getBranchesQueryOptions());
}
