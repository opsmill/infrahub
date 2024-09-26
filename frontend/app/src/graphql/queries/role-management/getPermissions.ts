import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_PERMISSIONS = gql`
  query {
    CoreBasePermission {
      edges {
        node {
          id
          display_label
          roles {
            count
          }
          ... on CoreObjectPermission {
            decision {
              value
            }
          }
          __typename
        }
      }
    }
  }
`;
