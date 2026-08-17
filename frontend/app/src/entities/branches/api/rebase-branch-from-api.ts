import { graphql, graphqlClient } from "@/shared/api/graphql/client";

const BRANCH_REBASE = graphql(`
  mutation BRANCH_REBASE($name: String, $waitUntilCompletion: Boolean!) {
    BranchRebase(wait_until_completion: $waitUntilCompletion, data: { name: $name }) {
      ok
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
        schema_differs_from_default_branch
      }
      task {
        id
      }
    }
  }
`);

export type RebaseBranchFromApiParams = {
  branchName: string;
  waitUntilCompletion: boolean;
};

export const rebaseBranchFromApi = ({
  branchName,
  waitUntilCompletion,
}: RebaseBranchFromApiParams) => {
  return graphqlClient.mutate({
    mutation: BRANCH_REBASE,
    variables: { name: branchName, waitUntilCompletion },
  });
};
