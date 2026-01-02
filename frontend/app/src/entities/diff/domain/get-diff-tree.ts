import { infiniteQueryOptions, useInfiniteQuery } from "@tanstack/react-query";
import type { graphql } from "gql.tada";

import type { DiffTree } from "@/shared/api/graphql/generated/graphql";
import type { PaginationParams } from "@/shared/api/types";

import { getDiffTreeFromApi } from "@/entities/diff/api/get-diff-tree-from-api";
import { treeQueryKeys } from "@/entities/diff/domain/diff.query-keys";

export const DIFF_TREE_PER_PAGE = 300;

export interface GetDiffTreeParams
  extends PaginationParams,
    GetDiffTreeInfiniteQueryOptionsParams {}

export type GetDiffTree = (params: GetDiffTreeParams) => Promise<DiffTree | null>;

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
  filters?: ReturnType<typeof graphql.scalar<"DiffTreeQueryFilters">>;
};

export const getDiffTreeInfiniteQueryOptions = ({
  branchName,
  filters,
}: GetDiffTreeInfiniteQueryOptionsParams) => {
  return infiniteQueryOptions({
    queryKey: treeQueryKeys.allWithContext({ branchName, filters }),
    queryFn: ({ pageParam }) => getDiffTree({ branchName, filters, offset: pageParam }),
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
