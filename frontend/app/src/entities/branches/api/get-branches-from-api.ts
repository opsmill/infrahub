import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

import { GET_BRANCHES, GET_BRANCHES_COUNT } from "@/entities/branches/api/get-branches-query";

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

export const getBranchesCountFromApi = async (branchName?: string) => {
  return graphqlClient.query({
    query: GET_BRANCHES_COUNT,
    variables: {
      branchName,
    },
  });
};
