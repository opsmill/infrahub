import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const GET_NUMBER_POOLS = graphql(`
  query GET_NUMBER_POOLS($objectKinds: [String]) {
    CoreNumberPool(node__values: $objectKinds) {
      edges {
        node {
          id
          hfid
          display_label
          node {
            id
            value
          }
          node_attribute {
            id
            value
          }
        }
      }
    }
  }
`);

type QueryVariables = VariablesOf<typeof GET_NUMBER_POOLS>;

export interface GetNumberPoolsFromApiParams extends ContextParams {
  objectKinds: Array<string>;
}

export function getNumberPoolsFromApi({
  objectKinds,
  branchName,
  atDate,
}: GetNumberPoolsFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOLS,
    variables: {
      objectKinds,
    } satisfies QueryVariables,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
