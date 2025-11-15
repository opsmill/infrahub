import { queryOptions, useQuery } from "@tanstack/react-query";

import { getBranches } from "./get-branches";

export function getBranchesQueryOptions() {
  return queryOptions({
    queryKey: [],
    queryFn: getBranches,
  });
}

export function useGetBranches() {
  return useQuery(getBranchesQueryOptions());
}
