import type { PaginationParams } from "@/shared/api/types";

import {
  type DiffTreeFilters,
  getDiffTreeFromApi,
} from "@/entities/diff/api/get-diff-tree-from-api";

export const DIFF_TREE_PER_PAGE = 300;

export type GetDiffTreeInfiniteQueryOptionsParams = {
  branchName: string;
  filters?: DiffTreeFilters;
  proposedChangeId?: string;
};

export interface GetDiffTreeParams
  extends PaginationParams,
    GetDiffTreeInfiniteQueryOptionsParams {}

type GetDiffTreeResult = Awaited<ReturnType<typeof getDiffTreeFromApi>>["data"]["DiffTree"];

export const getDiffTree = async ({
  branchName,
  limit = DIFF_TREE_PER_PAGE,
  offset,
  filters,
  proposedChangeId,
}: GetDiffTreeParams): Promise<GetDiffTreeResult> => {
  const { data } = await getDiffTreeFromApi({
    branchName,
    limit,
    offset,
    filters,
    proposedChangeId,
  });

  return data.DiffTree;
};
