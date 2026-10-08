import { type UseQueryResult, useQueries, useQuery } from "@tanstack/react-query";

import type {
  BranchGitRepository,
  BranchGitRepositoryPage,
} from "@/entities/branch-git-status/domain/model/branch-git-repository";
import {
  type BranchGitStatus,
  BranchGitStatusError,
} from "@/entities/branch-git-status/domain/model/branch-git-status";
import type { RepositoryBranchStatusPage } from "@/entities/branch-git-status/domain/model/repository-branch-status";
import { getUnknownSyncStatus } from "@/entities/branch-git-status/domain/rules/get-unknown-sync-status";
import {
  type RepositoryListFetch,
  type RepositoryStatusFetch,
  summarizeBranchGitStatuses,
} from "@/entities/branch-git-status/domain/rules/summarize-branch-git-statuses";
import { getBranchGitRepositoriesQueryOptions } from "@/entities/branch-git-status/ui/queries/get-branch-git-repositories.query";
import { getRepositoryBranchStatusQueryOptions } from "@/entities/branch-git-status/ui/queries/get-repository-branch-status.query";
import {
  GENERIC_REPOSITORY_KIND,
  REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME,
} from "@/entities/repository/domain/model/repository";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const REPOSITORY_LIST_LIMIT = 500;
const BRANCH_STATUS_LIST_LIMIT = 500;

function isDenied(error: Error): boolean {
  return error instanceof BranchGitStatusError && error.code === "PERMISSION_DENIED";
}

// Data first: a failed background refetch keeps the list that was already loaded.
function getRepositoryListFailure(
  list: UseQueryResult<BranchGitRepositoryPage>
): Exclude<RepositoryListFetch, { status: "ok" }> | null {
  if (list.data) {
    const { repositories, count } = list.data;
    if (count <= repositories.length) return null;
    return {
      status: "error",
      message: `Only the first ${repositories.length} of ${count} repositories were read. Open the branch for the full list.`,
    };
  }
  if (!list.error) return { status: "pending" };
  if (isDenied(list.error)) return { status: "denied" };
  return { status: "error", message: list.error.message };
}

function toRepositoryStatusFetch(
  repository: BranchGitRepository,
  result: UseQueryResult<RepositoryBranchStatusPage> | undefined
): RepositoryStatusFetch {
  if (result?.data) {
    return { status: "ok", repository, rows: result.data.rows, count: result.data.count };
  }
  if (!result?.error) return { status: "pending", repository };
  if (isDenied(result.error)) return { status: "denied", repository };
  return { status: "error", repository, message: result.error.message };
}

export function useGetBranchGitStatuses(
  branchNames: readonly string[]
): Record<string, BranchGitStatus> {
  const { schema } = useSchema(GENERIC_REPOSITORY_KIND);
  const unknownSyncStatus = getUnknownSyncStatus(
    schema?.attributes?.find(({ name }) => name === REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME)?.choices
  );

  const repositoryList = useQuery(
    getBranchGitRepositoriesQueryOptions({ limit: REPOSITORY_LIST_LIMIT, offset: 0 })
  );
  const listFailure = getRepositoryListFailure(repositoryList);
  const repositories = listFailure ? [] : (repositoryList.data?.repositories ?? []);

  return useQueries({
    queries: repositories.map(({ id }) =>
      getRepositoryBranchStatusQueryOptions({ repositoryId: id, limit: BRANCH_STATUS_LIST_LIMIT })
    ),
    // Keyed by branch name, so an unchanged branch keeps its status object across refetches.
    combine: (results) =>
      summarizeBranchGitStatuses(
        branchNames,
        listFailure ?? {
          status: "ok",
          statuses: repositories.map((repository, index) =>
            toRepositoryStatusFetch(repository, results[index])
          ),
        },
        unknownSyncStatus
      ),
  });
}
