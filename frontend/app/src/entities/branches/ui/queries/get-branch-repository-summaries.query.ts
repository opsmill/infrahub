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
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";
import { compareSyncStatusSeverity } from "@/entities/repository/domain/rules/sync-status-severity";
import { getBranchRepositoriesQueryOptions } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { getRepositoryBranchStatusQueryOptions } from "@/entities/repository/ui/queries/get-repository-branch-status.query";

const REPOSITORY_FETCH_LIMIT = 500;
const REPOSITORY_BRANCH_STATUS_LIMIT = 500;

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
      message: `Only the first ${repositories.length} of ${count} repositories were read. Open the branch for the full list.`,
    };
  }
  if (!list.error) return { status: "pending" };
  return toFailedFetch(list.error);
}

function getListFetch(
  allBranches: BranchListItem[] | undefined,
  branchesError: Error | null,
  defaultBranch: BranchListItem | null,
  repositoryList: UseQueryResult<BranchRepositoryPage>
): RepositoryStatusFetch | null {
  if (branchesError && !allBranches) return { status: "error", message: branchesError.message };
  if (allBranches && !defaultBranch) {
    return {
      status: "error",
      message: "No default branch found, so repositories could not be read.",
    };
  }
  return toRepositoryListFetch(repositoryList);
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

export function useGetBranchRepositorySummaries(
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
    // Only the ids are read here; each repository's status query polls while it syncs.
    refetchInterval: false,
  });
  const listFetch = getListFetch(allBranches, branchesError, defaultBranch, repositoryList);
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
          : repositories.map((repository, index): RepositoryStatusFetch => {
              const result = results[index];
              return result ? toStatusFetch(repository, result) : { status: "pending" };
            }),
        compareSyncStatusSeverity
      ),
  });
}
