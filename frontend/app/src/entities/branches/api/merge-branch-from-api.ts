import { graphql, graphqlClient } from "@/shared/api/graphql/client";

const BRANCH_MERGE = graphql(`
  mutation BRANCH_MERGE($name: String) {
    BranchMerge(wait_until_completion: false, data: { name: $name }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface MergeBranchFromApiParams {
  branchName: string;
}

export function mergeBranchFromApi({ branchName }: MergeBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_MERGE,
    variables: { name: branchName },
    context: { branch: branchName },
  });
}
