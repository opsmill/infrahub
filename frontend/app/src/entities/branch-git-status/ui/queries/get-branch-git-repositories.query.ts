import { queryOptions } from "@tanstack/react-query";

import { retryBackgroundQuery } from "@/shared/api/background-query";

import {
  type GetBranchGitRepositoriesParams,
  getBranchGitRepositories,
} from "@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories";
import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";

export function getBranchGitRepositoriesQueryOptions(params: GetBranchGitRepositoriesParams) {
  return queryOptions({
    queryKey: branchGitStatusQueryKeys.repositories(params),
    queryFn: () => getBranchGitRepositories(params),
    retry: retryBackgroundQuery,
  });
}
