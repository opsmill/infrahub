import { queryOptions, useQuery } from "@tanstack/react-query";
import React from "react";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";

import { getBranches } from "./get-branches";

export function getBranchesQueryOptions(id: string) {
  console.log("id: ", id);
  return queryOptions({
    queryKey: [...branchesQueryKeys.all, id],
    queryFn: getBranches,
  });
}

export function useGetBranches() {
  const id = React.useId();
  return useQuery(getBranchesQueryOptions(id));
}
