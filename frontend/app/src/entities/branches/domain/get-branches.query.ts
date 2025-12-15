import {
  infiniteQueryOptions,
  queryOptions,
  useInfiniteQuery,
  useQuery,
} from "@tanstack/react-query";

import type { PaginationParams } from "@/shared/api/types";

import { BRANCHES_PER_PAGE } from "@/entities/branches/api/get-branches-from-api";
import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import {
  type GetBranchesParams,
  getAllBranches,
  getBranches,
} from "@/entities/branches/domain/get-branches";
import { getBranchesCount } from "@/entities/branches/domain/get-branches-count";

type GetBranchesInfiniteQueryOptionsParams = Omit<GetBranchesParams, keyof PaginationParams>;

// Paginated query for branches list view
export function getBranchesInfiniteQueryOptions(
  params: GetBranchesInfiniteQueryOptionsParams = {}
) {
  return infiniteQueryOptions({
    queryKey: branchesQueryKeys.list(params),
    queryFn: ({ pageParam }) => {
      return getBranches({
        ...params,
        offset: pageParam,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage.length < BRANCHES_PER_PAGE) {
        return;
      }
      return lastPageParam + BRANCHES_PER_PAGE;
    },
  });
}

export function useGetBranchesPaginated(params: GetBranchesInfiniteQueryOptionsParams = {}) {
  return useInfiniteQuery(getBranchesInfiniteQueryOptions(params));
}

// Non-paginated query for branch selector and provider (fetches all branches)
// TODO: can be removed once we remove branchesState atom to use pagination within selectors
export function getAllBranchesQueryOptions() {
  return queryOptions({
    queryKey: branchesQueryKeys.all,
    queryFn: getAllBranches,
  });
}

export function useGetBranches() {
  return useQuery(getAllBranchesQueryOptions());
}

// Count query for branches list header badge
export function getBranchesCountQueryOptions(branchName?: string) {
  return queryOptions({
    queryKey: branchesQueryKeys.count(branchName),
    queryFn: () => getBranchesCount(branchName),
  });
}

export function useGetBranchesCount(branchName?: string) {
  return useQuery(getBranchesCountQueryOptions(branchName));
}
