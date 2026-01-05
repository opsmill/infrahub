import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const DIFF_UPDATE = gql`
  mutation DIFF_UPDATE($branchName: String!, $waitUntilCompletion: Boolean) {
    DiffUpdate(data: { branch: $branchName }, wait_until_completion: $waitUntilCompletion) {
      ok
    }
  }
`;

export type UpdateDiffFromApiParams = {
  branchName: string;
  waitUntilCompletion: boolean;
};

export const updateDiffFromApi = ({ branchName, waitUntilCompletion }: UpdateDiffFromApiParams) => {
  return graphqlClient.mutate({
    mutation: DIFF_UPDATE,
    variables: {
      branchName,
      waitUntilCompletion,
    },
  });
};
