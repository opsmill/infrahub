import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_DELETE = graphql(`
  mutation BRANCH_DELETE($name: String) {
    BranchDelete(data: { name: $name }) {
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
