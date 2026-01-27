import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_BRANCHES_COUNT = graphql(`
  query GetBranchesCount($nameValue: String, $partialMatch: Boolean, $statusValue: BranchStatus, $createdById: ID) {
    InfrahubBranch(name__value: $nameValue, partial_match: $partialMatch, status__value: $statusValue, node_metadata__created_by__id: $createdById) {
      count
    }
  }
`);

export type GetBranchesCountFromApiParams = VariablesOf<typeof GET_BRANCHES_COUNT>;

export const getBranchesCountFromApi = async ({
  nameValue,
  partialMatch,
  statusValue,
  createdById,
}: GetBranchesCountFromApiParams = {}) => {
  return graphqlClient.query({
    query: GET_BRANCHES_COUNT,
    variables: { nameValue, partialMatch, statusValue, createdById },
  });
};
