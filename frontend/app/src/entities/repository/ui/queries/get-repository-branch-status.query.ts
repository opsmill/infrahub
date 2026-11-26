import { queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRepositoryBranchStatusParams,
  getRepositoryBranchStatus,
} from "@/entities/repository/domain/use-cases/get-repository-branch-status";
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

function getRepositoryBranchStatusQueryOptions(params: GetRepositoryBranchStatusParams) {
  return queryOptions({
    queryKey: repositoryQueryKeys.branchStatus(params),
    queryFn: () => getRepositoryBranchStatus(params),
    // Held within one repository and branch only: it keeps the card from collapsing between pages,
    // while across either the rows would belong to a different object.
    placeholderData: (previousData, previousQuery) => {
      const previousParams = previousQuery?.queryKey.at(-1) as
        | GetRepositoryBranchStatusParams
        | undefined;
      const isSameObject =
        previousParams?.id === params.id && previousParams?.branchName === params.branchName;

      return isSameObject ? previousData : undefined;
    },
  });
}

export function useGetRepositoryBranchStatus(
  params: Omit<GetRepositoryBranchStatusParams, keyof BranchContextParams>
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery(
    getRepositoryBranchStatusQueryOptions({ ...params, branchName: currentBranch.name })
  );
}
