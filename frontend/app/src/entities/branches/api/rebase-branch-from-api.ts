import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

export const BRANCH_REBASE = gql`
  mutation BRANCH_REBASE($name: String, $waitForCompletion: Boolean!) {
    BranchRebase (
      wait_until_completion: $waitForCompletion
      data: {
        name: $name
      }
    ) {
      ok
      object {
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
      task {
        id
      }
    }
  }
`;

export type RebaseBranchFromApiParams = {
  branchName: string;
  waitForCompletion: boolean;
};

export const rebaseBranchFromApi = ({
  branchName,
  waitForCompletion,
}: RebaseBranchFromApiParams) => {
  return graphqlClient.mutate({
    mutation: BRANCH_REBASE,
    variables: { name: branchName, waitForCompletion },
  });
};
