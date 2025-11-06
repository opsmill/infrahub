import { gql } from "@apollo/client";

import type {
  Get_Resource_UtilizationQuery,
  Get_Resource_UtilizationQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const GET_RESOURCE_UTILIZATION = gql`
  query GET_RESOURCE_UTILIZATION($poolId: String!) {
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

export interface GetResourceUtilizationFromApiParams {
  resourceId: string;
}

export function getResourceUtilizationFromApi({ resourceId }: GetResourceUtilizationFromApiParams) {
  return graphqlClient.query<Get_Resource_UtilizationQuery, Get_Resource_UtilizationQueryVariables>(
    {
      query: GET_RESOURCE_UTILIZATION,
      variables: {
        poolId: resourceId,
      },
    }
  );
}
