import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const DIFF_UPDATE = graphql(`
  mutation DIFF_UPDATE($branchName: String!, $waitUntilCompletion: Boolean) {
    DiffUpdate(data: { branch: $branchName }, wait_until_completion: $waitUntilCompletion) {
      ok
    }
  }
`);

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
