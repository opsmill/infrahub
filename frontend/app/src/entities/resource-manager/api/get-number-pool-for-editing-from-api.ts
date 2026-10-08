import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

// Without a limit the server returns every range of the pool, so the list is never truncated.
const GET_NUMBER_POOL_FOR_EDITING = graphql(`
  query GET_NUMBER_POOL_FOR_EDITING($poolId: ID!) {
    CoreNumberPool(ids: [$poolId]) {
      edges {
        node {
          id
          name {
            value
          }
          description {
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
          pool_type {
            value
          }
          ranges {
            edges {
              node {
                id
                start {
                  value
                }
                end {
                  value
                }
                allocation_weight {
                  value
                }
              }
            }
          }
        }
      }
    }
  }
`);

export type NumberPoolForEditingNode = NonNullable<
  ResultOf<typeof GET_NUMBER_POOL_FOR_EDITING>["CoreNumberPool"]["edges"][number]["node"]
>;

export interface GetNumberPoolForEditingFromApiParams extends BranchContextParams {
  poolId: string;
}

export function getNumberPoolForEditingFromApi({
  poolId,
  branchName,
}: GetNumberPoolForEditingFromApiParams) {
  return graphqlClient.query({
    query: GET_NUMBER_POOL_FOR_EDITING,
    variables: { poolId },
    context: {
      branch: branchName,
    },
  });
}
