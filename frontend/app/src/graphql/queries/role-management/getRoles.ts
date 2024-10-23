import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ROLES = gql`
  query GET_ROLE_MANAGEMENT_ROLES {
    CoreAccountRole {
      count
      edges {
        node {
          id
          name {
            value
          }
          groups {
            count
            edges {
              node {
                id
                display_label
              }
            }
          }
          permissions {
            count
            edges {
              node {
                id
                display_label
                identifier {
                  value
                }
              }
            }
          }
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
