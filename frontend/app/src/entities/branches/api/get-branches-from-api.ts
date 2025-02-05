import { gql } from "@/shared/api/graphql/generated";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_BRANCHES = gql(/* GraphQL */ `
  query GetBranches {
    Branch {
      id
      name
      description
      origin_branch
      branched_from
      created_at
      sync_with_git
      is_default
      has_schema_changes
    }
  }
`);

export const getBranchesFromApi = async () => {
  return graphqlClient.query({
    query: GET_BRANCHES,
  });
};
