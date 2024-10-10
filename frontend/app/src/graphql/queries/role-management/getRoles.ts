import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ROLES = gql`
  query GET_ROLE_MANAGEMENT_ROLES {
    CoreAccountRole {
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
              }
            }
          }
          permissions {
            count
            edges {
              node {
                id
              }
            }
          }
        }
      }
    }
  }
`;
