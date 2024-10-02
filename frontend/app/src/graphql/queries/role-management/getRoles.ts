import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ROLES = gql`
  query GET_ROLE_MANAGEMENT_ROLES {
    CoreAccountRole {
      edges {
        node {
          id
          display_label
          groups {
            count
          }
          permissions {
            count
          }
        }
      }
    }
  }
`;
