import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_NUMBER_POOL = graphql(`
  query GET_NUMBER_POOL($ids: [ID]) {
    CoreNumberPool(ids: $ids) {
      edges {
        node {
          id
          hfid
          display_label
          __typename
          name {
            value
          }
          description {
            value
          }
          pool_type {
            value
          }
          node {
            value
          }
          node_attribute {
            value
          }
          allocation_scope {
            value
          }
        }
      }
    }
  }
`);

export type NumberPoolNode = NonNullable<
  NonNullable<ResultOf<typeof GET_NUMBER_POOL>["CoreNumberPool"]["edges"][number]>["node"]
>;

export interface GetNumberPoolFromApiParams extends ContextParams {
  poolId: string;
}

export function getNumberPoolFromApi({ poolId, branchName, atDate }: GetNumberPoolFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL,
    variables: {
      ids: [poolId],
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
