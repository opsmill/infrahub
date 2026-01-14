import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_BRANCHES_COUNT = graphql(`
  query GetBranchesCount($branchSearch: String) {
    InfrahubBranch(name__value: $branchSearch) {
      count
    }
  }
`);

interface GetBranchesCountFromApiParams extends VariablesOf<typeof GET_BRANCHES_COUNT> {}

export const getBranchesCountFromApi = async (variables: GetBranchesCountFromApiParams) => {
  return graphqlClient.query({
    query: GET_BRANCHES_COUNT,
    variables,
  });
};
