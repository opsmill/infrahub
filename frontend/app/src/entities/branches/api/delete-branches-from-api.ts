import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCHES_DELETE = graphql(`
  mutation BRANCHES_DELETE($names: [String]!) {
    BranchDelete(data: { names: $names }) {
      ok
    }
  }
`);

export type DeleteBranchesFromApiParams = VariablesOf<typeof BRANCHES_DELETE>;

export function deleteBranchesFromApi(params: DeleteBranchesFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCHES_DELETE,
    variables: params,
  });
}
