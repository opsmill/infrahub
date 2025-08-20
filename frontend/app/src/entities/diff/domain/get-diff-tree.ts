import { getDiffTreeFromApi } from "@/entities/diff/api/get-diff-tree-from-api";
import { DiffTree, DiffTreeQueryFilters } from "@/shared/api/graphql/generated/graphql";
import { PaginationParams } from "@/shared/api/types";
import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";

export const DIFF_TREE_PER_PAGE = 300;

export type GetDiffTreeParams = PaginationParams & {
  branchName: string;
  filters?: DiffTreeQueryFilters;
};

export type GetDiffTree = (params: GetDiffTreeParams) => Promise<DiffTree>;

export const getDiffTree: GetDiffTree = async ({
  branchName,
  limit = DIFF_TREE_PER_PAGE,
  offset,
  filters,
}) => {
  const { data } = await getDiffTreeFromApi({ branchName, limit, offset, filters });

  return data.DiffTree;
};

export type GetDiffTreeInfiniteQueryOptionsParams = {
  branchName: string;
  filters?: DiffTreeQueryFilters;
};

export const getDiffTreeInfiniteQueryOptions = ({
  branchName,
  filters,
}: GetDiffTreeInfiniteQueryOptionsParams) => {
  return infiniteQueryOptions({
    queryKey: ["diff-tree", branchName, filters],
    queryFn: ({ pageParam }) => getDiffTree({ branchName, filters, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _, lastPageParam) => {
      if (lastPage === null || (lastPage?.nodes && lastPage.nodes.length < DIFF_TREE_PER_PAGE)) {
        return undefined;
      }
      return lastPageParam + DIFF_TREE_PER_PAGE;
    },
  });
};

export const useDiffTreeInfiniteQuery = (params: GetDiffTreeInfiniteQueryOptionsParams) => {
  return useInfiniteQuery(getDiffTreeInfiniteQueryOptions(params));
};
