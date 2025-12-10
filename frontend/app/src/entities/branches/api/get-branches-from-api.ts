import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { GET_BRANCHES } from "@/entities/branches/api/query/get-branches-query";

export const getBranchesFromApi = async (branchName?: string) => {
  return graphqlClient.query({
    query: GET_BRANCHES,
    variables: { branchName },
  });
};
