import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS = gql`
  query {
    CoreGlobalPermission {
      edges {
        node {
          id
          display_label
          roles {
            count
          }
          identifier {
            value
          }
          __typename
        }
      }
    }
  }
`;
