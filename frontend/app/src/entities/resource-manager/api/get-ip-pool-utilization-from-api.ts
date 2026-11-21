import { graphql, graphqlClient, type ResultOf } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const GET_IP_POOL_UTILIZATION = graphql(`
  query GET_IP_POOL_UTILIZATION($poolId: String!) {
    InfrahubResourcePoolUtilization(pool_id: $poolId) {
      edges {
        node {
          id
          display_label
          kind
          utilization
          utilization_branches
          utilization_default_branch
        }
      }
      count
      utilization
      utilization_branches
      utilization_default_branch
    }
  }
`);

export type IpPoolUtilizationNode = ResultOf<
  typeof GET_IP_POOL_UTILIZATION
>["InfrahubResourcePoolUtilization"];

export interface GetIpPoolUtilizationFromApiParams extends ContextParams {
  poolId: string;
}

export function getIpPoolUtilizationFromApi({
  poolId,
  branchName,
  atDate,
}: GetIpPoolUtilizationFromApiParams) {
  return graphqlClient.query({
    query: GET_IP_POOL_UTILIZATION,
    variables: { poolId },
    context: { branch: branchName, date: atDate },
  });
}
