import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_IP_POOL_RESOURCE_WEIGHTS = graphql(`
  query GET_IP_POOL_RESOURCE_WEIGHTS($resourceIds: [ID]) {
    CoreWeightedPoolResource(ids: $resourceIds) {
      edges {
        node {
          id
          allocation_weight {
            value
          }
        }
      }
    }
  }
`);

export interface GetIpPoolResourceWeightsFromApiParams extends ContextParams {
  resourceIds: string[];
}

export function getIpPoolResourceWeightsFromApi({
  resourceIds,
  branchName,
  atDate,
}: GetIpPoolResourceWeightsFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_POOL_RESOURCE_WEIGHTS,
    variables: { resourceIds },
    context: { branch: branchName, date: atDate },
  });
}
