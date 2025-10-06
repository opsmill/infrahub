import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export const GET_NUMBER_POOLS = gql`
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
`;

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
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
