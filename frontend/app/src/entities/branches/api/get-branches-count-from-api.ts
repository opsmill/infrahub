import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { GET_BRANCHES_COUNT } from "@/entities/branches/api/get-branches-count-query";

export const getBranchesCountFromApi = async (branchName?: string) => {
  return graphqlClient.query({
    query: GET_BRANCHES_COUNT,
    variables: {
      branchName,
    },
  });
};
