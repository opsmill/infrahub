import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const BRANCH_DELETE = graphql(`
  mutation BRANCH_DELETE($name: String, $deleteFromGit: Boolean) {
    BranchDelete(data: { name: $name, delete_from_git: $deleteFromGit }) {
      ok
    }
  }
`);

export type DeleteBranchFromApiParams = VariablesOf<typeof BRANCH_DELETE>;

export function deleteBranchFromApi(params: DeleteBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_DELETE,
    variables: params,
  });
}
