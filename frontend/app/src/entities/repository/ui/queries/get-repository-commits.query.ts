import {
  type InfiniteData,
  infiniteQueryOptions,
  type UseInfiniteQueryOptions,
  useInfiniteQuery,
} from "@tanstack/react-query";

import type { ContextParams, PaginationParams } from "@/shared/api/types";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import { shouldRetryGitUnavailable } from "@/entities/repository/domain/rules/should-retry-git-unavailable";
import {
  type GetRepositoryCommitsParams,
  getRepositoryCommits,
} from "@/entities/repository/domain/use-cases/get-repository-commits";
import {
  type RepositoryKeyParams,
  repositoriesQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_COMMITS_MAX_RETRIES,
  REPOSITORY_COMMITS_PAGE_SIZE,
  REPOSITORY_COMMITS_RETRY_DELAY_MS,
  REPOSITORY_COMMITS_STALE_TIME_MS,
} from "@/entities/repository/ui/queries/repository-commits.constants";

type GetRepositoryCommitsQueryParams = Omit<GetRepositoryCommitsParams, keyof PaginationParams>;

type RepositoryCommitPages = InfiniteData<RepositoryCommitLog, number>;

export function getRepositoryCommitsQueryKey({ repositoryId, branchName }: RepositoryKeyParams) {
  return repositoriesQueryKeys.commits({
    repositoryId,
    branchName,
    limit: REPOSITORY_COMMITS_PAGE_SIZE,
  });
}

function isWarmingUp(error: Error) {
  return error instanceof RepositoryGitUnavailableError && shouldRetryGitUnavailable(error.reason);
}

type RepositoryCommitsQueryKey = ReturnType<typeof getRepositoryCommitsQueryKey>;

export function getRepositoryCommitsQueryOptions<TData = RepositoryCommitPages>(
  params: GetRepositoryCommitsQueryParams
) {
  return infiniteQueryOptions<RepositoryCommitLog, Error, TData, RepositoryCommitsQueryKey, number>(
    {
      queryKey: getRepositoryCommitsQueryKey(params),
      queryFn: ({ pageParam }) =>
        getRepositoryCommits({ ...params, offset: pageParam, limit: REPOSITORY_COMMITS_PAGE_SIZE }),
      initialPageParam: 0,
      getNextPageParam: (lastPage, _, lastPageParam) => {
        if (lastPage.commits.length < REPOSITORY_COMMITS_PAGE_SIZE) return;
        return lastPageParam + REPOSITORY_COMMITS_PAGE_SIZE;
      },
      // Retried, not polled: an interval refetch with no data resets the query to pending and clears its error.
      // Capped because a clone that failed for good keeps answering NOT_CLONED.
      retry: (failureCount, error) =>
        failureCount < REPOSITORY_COMMITS_MAX_RETRIES && isWarmingUp(error),
      retryDelay: REPOSITORY_COMMITS_RETRY_DELAY_MS,
      // Every loaded page is a worker round trip, and a focus or remount refetch replays all of them.
      refetchOnWindowFocus: false,
      staleTime: REPOSITORY_COMMITS_STALE_TIME_MS,
    }
  );
}

export type UseGetRepositoryCommitsConfig<TData> = Omit<
  UseInfiniteQueryOptions<RepositoryCommitLog, Error, TData, RepositoryCommitsQueryKey, number>,
  "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
>;

export function useGetRepositoryCommits<TData = RepositoryCommitPages>(
  params: Omit<GetRepositoryCommitsQueryParams, keyof ContextParams>,
  config: UseGetRepositoryCommitsConfig<TData> = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useInfiniteQuery({
    ...getRepositoryCommitsQueryOptions<TData>({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
