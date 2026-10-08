import { queryOptions } from "@tanstack/react-query";

import {
  type GetBranchGitRepositoriesParams,
  getBranchGitRepositories,
} from "@/entities/branch-git-status/domain/use-cases/get-branch-git-repositories";
import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { BRANCH_GIT_STATUS_STALE_TIME_MS } from "@/entities/branch-git-status/ui/queries/branch-git-status-stale-time";

export function getBranchGitRepositoriesQueryOptions(params: GetBranchGitRepositoriesParams) {
  return queryOptions({
    queryKey: branchGitStatusQueryKeys.repositories(params),
    queryFn: () => getBranchGitRepositories(params),
    staleTime: BRANCH_GIT_STATUS_STALE_TIME_MS,
  });
}
