import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_BRANCHES = gql`
  query GetBranches {
    Branch {
      id
      name
      description
      origin_branch
      branched_from
      status
      created_at
      sync_with_git
      is_default
      has_schema_changes
    }
  }
`;

export const getBranchesFromApi = async () => {
  return graphqlClient.query({
    query: GET_BRANCHES,
  });
};
