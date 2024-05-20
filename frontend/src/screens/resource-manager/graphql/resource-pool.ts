import { gql } from "@apollo/client";

export const GET_KIND_FOR_RESOURCE_POOL = gql`
  query GET_KIND_FOR_RESOURCE_POOL($ids: [ID]) {
    CoreResourcePool(ids: $ids) {
      edges {
        node {
          id
          display_label
          __typename
        }
      }
    }
  }
`;

export const GET_RESOURCE_POOL_UTILIZATION = gql`
  query GET_RESOURCE_POOL_UTILIZATION($poolId: String!) {
    InfrahubResourcePoolUtilization(pool_id: $poolId) {
      edges {
        node {
          id
          display_label
          kind
          weight
          utilization
          utilization_default_branch
        }
      }
      count
      utilization
      utilization_default_branch
    }
  }
`;
