import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

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
        status
        schema_differs_from_default_branch
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
