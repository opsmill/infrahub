import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_VALIDATE = graphql(`
  mutation BRANCH_VALIDATE($name: String) {
    BranchValidate(wait_until_completion: false, data: { name: $name }) {
      ok
      task {
        id
      }
    }
  }
`);

export interface ValidateBranchFromApiParams {
  branchName: string;
}

export function validateBranchFromApi({ branchName }: ValidateBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_VALIDATE,
    variables: { name: branchName },
    context: { branch: branchName },
  });
}
