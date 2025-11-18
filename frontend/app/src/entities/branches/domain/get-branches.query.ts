import { queryOptions, useQuery } from "@tanstack/react-query";
import React from "react";

import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";

import { getBranches } from "./get-branches";

export function getBranchesQueryOptions(id: string) {
  // biome-ignore lint/suspicious/noConsole: <trying to fix flaky tests>
  console.log("id: ", id);
  return queryOptions({
    queryKey: branchesQueryKeys.all,
    queryFn: getBranches,
    refetchOnMount: "always",
  });
}

export function useGetBranches() {
  const id = React.useId();
  return useQuery(getBranchesQueryOptions(id));
}
