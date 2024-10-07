import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_GROUPS = gql`
  query GET_ROLE_MANAGEMENT_GROUPS {
    CoreAccountGroup {
      edges {
        node {
          id
          name {
            value
          }
          description {
            value
          }
          group_type {
            value
          }
          members {
            edges {
              node {
                display_label
              }
            }
          }
        }
      }
    }
  }
`;
