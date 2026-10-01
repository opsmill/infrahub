import { queryOptions, useQuery } from "@tanstack/react-query";

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
    // and the row area from collapsing on every page change. Held only within one repository and
    // branch: across either, the rows belong to a different object and would be shown under its
    // header as if they were its own.
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
    getRepositoryBranchStatusQueryOption({ ...params, branchName: currentBranch.name })
  );
}
