import { type UseQueryResult, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import type {
  BranchRepositoryRef,
  BranchRepositorySummary,
} from "@/entities/branches/domain/model/branch-repository-summary";
import { findSelectedBranch } from "@/entities/branches/domain/rules/find-selected-branch";
import {
  findBranchesAbsentFromEveryPage,
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
import { repositoryQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

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
  if (list.error instanceof BranchRepositoriesError && list.error.code === "PERMISSION_DENIED") {
    return { status: "denied" };
  }
  return { status: "error", message: list.error.message };
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

  // For each branch, the oldest status read already answered when the branch first showed up: a page read
  // no later than that may predate the branch, so its absence there is not yet an answer.
  const [lastReadAtFirstSight, setLastReadAtFirstSight] = useState<Record<string, number>>({});

  const status = useQueries({
    queries: repositories.map(({ id }) =>
      getRepositoryBranchStatusQueryOptions({
        id,
        branchName: defaultBranchName,
        limit: REPOSITORY_BRANCH_STATUS_LIMIT,
      })
    ),
    combine: (results) => {
      const fetches = listFetch
        ? [listFetch]
        : results.map((result, index) => toStatusFetch(repositories[index]!, result));
      // A failed read counts as answered too, so a failing refetch is not re-triggered in a loop.
      const lastReadAt =
        results.length > 0
          ? Math.min(...results.map((r) => Math.max(r.dataUpdatedAt, r.errorUpdatedAt)))
          : 0;
      const unconfirmed = findBranchesAbsentFromEveryPage(branches, fetches).filter(
        (name) => !(name in lastReadAtFirstSight) || lastReadAt <= lastReadAtFirstSight[name]!
      );
      return {
        summaries: summarizeBranchRepositories(
          branches,
          fetches,
          compareSyncStatusSeverity,
          unconfirmed
        ),
        lastReadAt,
        unconfirmedKey: unconfirmed.join("\n"),
        isFetching: results.some((result) => result.isFetching),
      };
    },
  });

  const unseen = branches.filter(({ name }) => !(name in lastReadAtFirstSight));
  if (unseen.length > 0) {
    setLastReadAtFirstSight({
      ...lastReadAtFirstSight,
      ...Object.fromEntries(unseen.map(({ name }) => [name, status.lastReadAt])),
    });
  }

  const queryClient = useQueryClient();
  const { unconfirmedKey, isFetching } = status;
  useEffect(() => {
    if (!unconfirmedKey || isFetching) return;
    queryClient.invalidateQueries({ queryKey: repositoryQueryKeys.branchStatuses() });
  }, [unconfirmedKey, isFetching, queryClient]);

  return status.summaries;
}
