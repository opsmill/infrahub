import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

import { GET_BRANCHES_COUNT } from "@/entities/branches/api/get-branches-count-query";

export const BRANCHES_PER_PAGE = 40;

export interface GetBranchesFromApiParams extends PaginationParams {
  branchName?: string;
}

export const getBranchesCountFromApi = async (branchName?: string) => {
  return graphqlClient.query({
    query: GET_BRANCHES_COUNT,
    variables: {
      branchName,
    },
  });
};
