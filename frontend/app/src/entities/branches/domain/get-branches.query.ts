import { queryOptions, useQuery } from "@tanstack/react-query";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";

import { getBranches } from "./get-branches";

export function getBranchesQueryOptions(search?: string) {
  return queryOptions({
    queryKey: branchesQueryKeys.list(search),
    queryFn: () => getBranches(search),
  });
}

export function useGetBranches(search?: string) {
  return useQuery(getBranchesQueryOptions(search));
}

export function getBranchesCountQueryOptions(search?: string) {
  return queryOptions({
    queryKey: branchesQueryKeys.count(search),
    queryFn: async () => {
      const branches = await getBranches(search);
      return branches.length;
    },
  });
}

export function useGetBranchesCount(search?: string) {
  return useQuery(getBranchesCountQueryOptions(search));
}
