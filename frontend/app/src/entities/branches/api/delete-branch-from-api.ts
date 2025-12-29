import { gql } from "@apollo/client";

import type {
  Branch_DeleteMutation,
  Branch_DeleteMutationVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const BRANCH_DELETE = gql`
  mutation BRANCH_DELETE($name: String) {
    BranchDelete(data: { name: $name }) {
      ok
    }
  }
`;

export interface DeleteBranchFromApiParams {
  name: string;
}

export function deleteBranchFromApi(params: DeleteBranchFromApiParams) {
  return graphqlClient.mutate<Branch_DeleteMutation, Branch_DeleteMutationVariables>({
    mutation: BRANCH_DELETE,
    variables: params,
  });
}
