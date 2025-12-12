import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

import { GET_BRANCHES } from "@/entities/branches/api/get-branches-query";

export const BRANCHES_PER_PAGE = 40;

export interface GetBranchesFromApiParams extends PaginationParams {
  branchName?: string;
}

export const getBranchesFromApi = async ({
  branchName,
  limit = BRANCHES_PER_PAGE,
  offset,
}: GetBranchesFromApiParams = {}) => {
  return graphqlClient.query({
    query: GET_BRANCHES,
    variables: {
      branchName,
      limit,
      offset,
    },
  });
};
