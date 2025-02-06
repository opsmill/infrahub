import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

export const DIFF_UPDATE = gql`
  mutation DIFF_UPDATE($branchName: String!, $waitForCompletion: Boolean) {
    DiffUpdate(data: { branch: $branchName, wait_for_completion: $waitForCompletion }) {
      ok
    }
  }
`;

export type UpdateDiffFromApiParams = {
  branchName: string;
  waitForCompletion: boolean;
};

export const updateDiffFromApi = ({ branchName, waitForCompletion }: UpdateDiffFromApiParams) => {
  return graphqlClient.mutate({
    mutation: DIFF_UPDATE,
    variables: {
      branchName,
      waitForCompletion,
    },
  });
};
