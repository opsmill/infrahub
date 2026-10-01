import {
  type InfiniteData,
  infiniteQueryOptions,
  replaceEqualDeep,
  useInfiniteQuery,
} from "@tanstack/react-query";

import type { ContextParams, InfiniteQueryConfig, PaginationParams } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type {
  RepositoryCommitLog,
  RepositoryCommitStatus,
} from "@/entities/repository/domain/model/repository";
import { getCommitStatusFromLog } from "@/entities/repository/domain/rules/get-commit-status-from-log";
import { isGitStateAvailable } from "@/entities/repository/domain/rules/is-git-state-available";
import {
  type GetRepositoryCommitsParams,
  getRepositoryCommits,
} from "@/entities/repository/domain/use-cases/get-repository-commits";
import { keepStatusOverColdAnswer } from "@/entities/repository/ui/queries/get-repository-commit-status.query";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export const REPOSITORY_COMMITS_PAGE_SIZE = 20;
export const REPOSITORY_COMMITS_POLL_INTERVAL_MS = 10_000;

type GetRepositoryCommitsQueryParams = Omit<GetRepositoryCommitsParams, keyof PaginationParams>;

type RepositoryCommitPages = InfiniteData<RepositoryCommitLog, number>;

function firstPageHasGitState({ pages: [firstPage] }: RepositoryCommitPages) {
  return firstPage !== undefined && isGitStateAvailable(firstPage);
}

// A same-key refetch replaces data outright, so without this a cold poll would blank loaded pages.
function keepLoadedPagesOverColdAnswer(
  oldData: RepositoryCommitPages | undefined,
  newData: RepositoryCommitPages
): RepositoryCommitPages {
  if (oldData && firstPageHasGitState(oldData) && !firstPageHasGitState(newData)) {
    return oldData;
  }
  return replaceEqualDeep(oldData, newData);
}

export function getRepositoryCommitsQueryOptions(params: GetRepositoryCommitsQueryParams) {
  return infiniteQueryOptions({
    queryKey: repositoriesQueryKeys.commits({
      repositoryId: params.repositoryId,
      branchName: params.branchName,
      limit: REPOSITORY_COMMITS_PAGE_SIZE,
    }),
    queryFn: async ({ pageParam, client }) => {
      const log = await getRepositoryCommits({
        ...params,
        offset: pageParam,
        limit: REPOSITORY_COMMITS_PAGE_SIZE,
      });
      if (pageParam === 0) {
        client.setQueryData<RepositoryCommitStatus>(
          repositoriesQueryKeys.commitStatus({
            repositoryId: params.repositoryId,
            branchName: params.branchName,
          }),
          (previous) => keepStatusOverColdAnswer(previous, getCommitStatusFromLog(log))
        );
      }
      return log;
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (
        !isGitStateAvailable(lastPage) ||
        lastPage.commits.length < REPOSITORY_COMMITS_PAGE_SIZE
      ) {
        return;
      }
      return lastPageParam + REPOSITORY_COMMITS_PAGE_SIZE;
    },
    refetchInterval: (query) => {
      const firstPage = query.state.data?.pages[0];
      return firstPage && !isGitStateAvailable(firstPage)
        ? REPOSITORY_COMMITS_POLL_INTERVAL_MS
        : false;
    },
    // TanStack types structuralSharing's arguments as unknown.
    structuralSharing: (oldData, newData) =>
      keepLoadedPagesOverColdAnswer(
        oldData as RepositoryCommitPages | undefined,
        newData as RepositoryCommitPages
      ),
    // Every loaded page is a worker round trip, and a focus refetch replays all of them.
    refetchOnWindowFocus: false,
  });
}

export type UseGetRepositoryCommitsConfig = InfiniteQueryConfig<
  typeof getRepositoryCommitsQueryOptions
>;

export function useGetRepositoryCommits(
  params: Omit<GetRepositoryCommitsQueryParams, keyof ContextParams>,
  config: UseGetRepositoryCommitsConfig = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useInfiniteQuery({
    ...getRepositoryCommitsQueryOptions({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
