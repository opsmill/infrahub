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

export const GET_RESOURCE_POOL_ALLOCATED = gql`
  query GET_RESOURCE_POOL_ALLOCATED(
    $poolId: String!
    $resourceId: String!
    $limit: Int
    $offset: Int
  ) {
    InfrahubResourcePoolAllocated(
      pool_id: $poolId
      resource_id: $resourceId
      limit: $limit
      offset: $offset
    ) {
      count
      edges {
        node {
          id
          display_label
          kind
          branch
          identifier
        }
      }
    }
  }
`;
