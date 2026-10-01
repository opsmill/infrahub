import { type UseQueryResult, useQueries } from "@tanstack/react-query";

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
import { REPOSITORY_FETCH_LIMIT } from "@/entities/repository/domain/model/repository";
import {
  RepositoryBranchStatusError,
  type RepositoryBranchStatusPage,
} from "@/entities/repository/domain/model/repository-branch-status";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { getRepositoryBranchStatusQueryOptions } from "@/entities/repository/ui/queries/get-repository-branch-status.query";

type RepositoryListQuery = ReturnType<typeof useGetBranchRepositories>;

function toRepositoryListFetch(list: RepositoryListQuery): RepositoryStatusFetch | null {
  if (list.data?.status === "denied") return { status: "denied" };
  if (list.data) return null;
  if (list.error) return { status: "error", message: list.error.message };
  return { status: "pending" };
}

// Data first: a failed background refetch keeps the rows that were already loaded.
function toStatusFetch(
  repository: BranchRepositoryRef,
  result: UseQueryResult<RepositoryBranchStatusPage>
): RepositoryStatusFetch {
  if (result.data) return { status: "ok", repository, rows: result.data.rows };
  if (!result.error) return { status: "pending" };
  if (
    result.error instanceof RepositoryBranchStatusError &&
    result.error.code === "PERMISSION_DENIED"
  ) {
    return { status: "denied" };
  }
  return { status: "error", message: result.error.message };
}

export function useBranchRepositorySummaries(
  branches: BranchListItem[]
): Record<string, BranchRepositorySummary> {
  const { data: allBranches } = useGetBranches();
  const defaultBranch = allBranches ? findSelectedBranch(allBranches, null) : null;
  const defaultBranchName = defaultBranch?.name ?? "";

  const repositoryList = useGetBranchRepositories(
    { branchName: defaultBranchName, syncWithGit: true },
    { enabled: Boolean(defaultBranch) }
  );
  const listFetch = toRepositoryListFetch(repositoryList);
  const repositories: BranchRepositoryRef[] =
    repositoryList.data?.status === "ok"
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
        limit: REPOSITORY_FETCH_LIMIT,
      })
    ),
    combine: (results) =>
      summarizeBranchRepositories(
        branches,
        listFetch
          ? [listFetch]
          : results.map((result, index) => toStatusFetch(repositories[index]!, result))
      ),
  });
}
