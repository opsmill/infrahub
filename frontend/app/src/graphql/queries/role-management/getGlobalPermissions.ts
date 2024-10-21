import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS = gql`
  query GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS {
    CoreGlobalPermission {
      edges {
        node {
          id
          display_label
          name {
            value
          }
          action {
            value
          }
          decision {
            value
          }
          roles {
            count
            edges {
              node {
                id
              }
            }
          }
          identifier {
            value
          }
          __typename
        }
      }
      permissions {
        edges {
          node {
            kind
            view
            create
            update
            delete
          }
        }
      }
    }
  }
`;
