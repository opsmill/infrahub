import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_CREATE = graphql(`
  mutation BRANCH_CREATE($name: String!, $description: String, $sync_with_git: Boolean) {
    BranchCreate(data: { name: $name, description: $description, sync_with_git: $sync_with_git }) {
      object {
        id
        name
        description
        origin_branch
        branched_from
        created_at
        status
        sync_with_git
        is_default
      }
    }
  }
`);

export type CreateBranchFromApiParams = VariablesOf<typeof BRANCH_CREATE>;

export function createBranchFromApi(params: CreateBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_CREATE,
    variables: params,
  });
}
