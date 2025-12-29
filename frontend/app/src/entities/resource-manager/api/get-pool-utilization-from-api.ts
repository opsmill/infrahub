import { gql } from "@apollo/client";

import type {
  Get_Pool_UtilizationQuery,
  Get_Pool_UtilizationQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const GET_POOL_UTILIZATION = gql`
  query GET_POOL_UTILIZATION($poolId: String!) {
    InfrahubResourcePoolUtilization(pool_id: $poolId) {
      edges {
        node {
          id
          display_label
          kind
          weight
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
`;

export interface GetPoolUtilizationFromApiParams {
  poolId: string;
}

export function getPoolUtilizationFromApi({ poolId }: GetPoolUtilizationFromApiParams) {
  return graphqlClient.query<Get_Pool_UtilizationQuery, Get_Pool_UtilizationQueryVariables>({
    query: GET_POOL_UTILIZATION,
    variables: {
      poolId,
    },
  });
}
