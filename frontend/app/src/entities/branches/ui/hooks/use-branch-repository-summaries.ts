import { type UseQueryResult, useQueries, useQuery } from "@tanstack/react-query";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoryRef,
  BranchRepositorySummary,
} from "@/entities/branches/domain/model/branch-repository-summary";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import {
  type RepositoryStatusFetch,
  summarizeBranchRepositories,
} from "@/entities/branches/domain/rules/summarize-branch-repositories";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import {
  BranchRepositoriesError,
  type BranchRepositoryPage,
} from "@/entities/repository/domain/model/branch-repository";
import {
  REPOSITORY_BRANCH_STATUS_LIMIT,
  REPOSITORY_FETCH_LIMIT,
} from "@/entities/repository/domain/model/repository";
import {
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";
import { compareSyncStatusSeverity } from "@/entities/repository/domain/rules/sync-status-severity";
import { getBranchRepositoriesQueryOptions } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { getRepositoryBranchStatusQueryOptions } from "@/entities/repository/ui/queries/get-repository-branch-status.query";

function toFailedFetch(error: Error): RepositoryStatusFetch {
  const isDenied =
    (error instanceof BranchRepositoriesError || error instanceof RepositoryBranchStatusError) &&
    error.code === "PERMISSION_DENIED";
  return isDenied ? { status: "denied" } : { status: "error", message: error.message };
}

// Data first: a failed background refetch keeps the list that was already loaded.
function toRepositoryListFetch(
  list: UseQueryResult<BranchRepositoryPage>
): RepositoryStatusFetch | null {
  if (list.data) {
    const { repositories, count } = list.data;
    if (count <= repositories.length) return null;
    return {
      status: "error",
      message: `Only the first ${repositories.length} of ${count} repositories were read. Open a branch for its full list.`,
    };
  }
  if (!list.error) return { status: "pending" };
  return toFailedFetch(list.error);
}

// Data first: a failed background refetch keeps the rows that were already loaded.
function toStatusFetch(
  repository: BranchRepositoryRef,
  result: UseQueryResult<RepositoryBranchStatusPage>
): RepositoryStatusFetch {
  if (result.data) {
    return { status: "ok", repository, rows: result.data.rows, count: result.data.count };
  }
  if (!result.error) return { status: "pending" };
  return toFailedFetch(result.error);
}

export function useBranchRepositorySummaries(
  branches: BranchListItem[]
): Record<string, BranchRepositorySummary> {
  const { data: allBranches, error: branchesError } = useGetBranches();
  const defaultBranch = allBranches ? findSelectedBranch(allBranches, null) : null;
  const defaultBranchName = defaultBranch?.name ?? "";

  const repositoryList = useQuery({
    ...getBranchRepositoriesQueryOptions({
      branchName: defaultBranchName,
      syncWithGit: true,
      isSyncing: false,
      limit: REPOSITORY_FETCH_LIMIT,
      offset: 0,
    }),
    enabled: Boolean(defaultBranch),
  });
  const listFetch =
    branchesError && !allBranches
      ? { status: "error" as const, message: branchesError.message }
      : toRepositoryListFetch(repositoryList);
  const repositories: BranchRepositoryRef[] =
    listFetch === null && repositoryList.data
      ? repositoryList.data.repositories.map(({ id, name, kind, isReadOnly }) => ({
          id,
          name,
          kind,
          isReadOnly,
        }))
      : [];

  return useQueries({
    queries: repositories.map(({ id }) =>
      getRepositoryBranchStatusQueryOptions({
        id,
        branchName: defaultBranchName,
        limit: REPOSITORY_BRANCH_STATUS_LIMIT,
      })
    ),
    combine: (results) =>
      summarizeBranchRepositories(
        branches,
        listFetch
          ? [listFetch]
          : results.map((result, index) => toStatusFetch(repositories[index]!, result)),
        compareSyncStatusSeverity
      ),
  });
}
