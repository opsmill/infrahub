import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

import {
  DIFF_TREE_PER_PAGE,
  type GetDiffTreeInfiniteQueryOptionsParams,
  getDiffTree,
} from "@/entities/diff/domain/get-diff-tree";
import { treeQueryKeys } from "@/entities/diff/ui/queries/diff.query-keys";

export const getDiffTreeInfiniteQueryOptions = ({
  branchName,
  filters,
  proposedChangeId,
}: GetDiffTreeInfiniteQueryOptionsParams) => {
  return infiniteQueryOptions({
    queryKey: treeQueryKeys.allWithContext({ branchName, filters, proposedChangeId }),
    queryFn: ({ pageParam }) =>
      getDiffTree({ branchName, filters, offset: pageParam, proposedChangeId }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage === null || (lastPage?.nodes && lastPage.nodes.length < DIFF_TREE_PER_PAGE)) {
        return;
      }
      return lastPageParam + DIFF_TREE_PER_PAGE;
    },
  });
};

export const useDiffTreeInfiniteQuery = (params: GetDiffTreeInfiniteQueryOptionsParams) => {
  return useInfiniteQuery(getDiffTreeInfiniteQueryOptions(params));
};
