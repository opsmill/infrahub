import { queryOptions, useQuery } from "@tanstack/react-query";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";

import { getBranches } from "./get-branches";

export function getBranchesQueryOptions() {
  return queryOptions({
    queryKey: branchesQueryKeys.all,
    queryFn: getBranches,
    refetchOnMount: "always",
  });
}

export function useGetBranches() {
  return useQuery(getBranchesQueryOptions());
}
