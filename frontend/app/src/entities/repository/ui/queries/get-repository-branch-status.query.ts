import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRepositoryBranchStatusParams,
  getRepositoryBranchStatus,
} from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

function getRepositoryBranchStatusQueryOption(params: GetRepositoryBranchStatusParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branchStatus(params),
    queryFn: () => getRepositoryBranchStatus(params),
    // Keeping the previous page rendered while the next one loads is what stops the pagination bar
    // and the row area from collapsing on every page change.
    placeholderData: keepPreviousData,
  });
}

export function useGetRepositoryBranchStatus(
  params: Omit<GetRepositoryBranchStatusParams, keyof BranchContextParams>
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery(
    getRepositoryBranchStatusQueryOption({ ...params, branchName: currentBranch.name })
  );
}
