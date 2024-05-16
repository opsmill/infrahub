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
