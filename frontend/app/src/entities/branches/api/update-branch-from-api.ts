import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_UPDATE = graphql(`
  mutation BRANCH_UPDATE($name: String!, $description: String) {
    BranchUpdate(data: { name: $name, description: $description }) {
      ok
    }
  }
`);

export type UpdateBranchFromApiParams = VariablesOf<typeof BRANCH_UPDATE>;

export function updateBranchFromApi(params: UpdateBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_UPDATE,
    variables: params,
  });
}
