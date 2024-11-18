import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_GROUPS = gql`
  query GET_ROLE_MANAGEMENT_GROUPS($search: String) {
    CoreAccountGroup(any__value: $search, partial_match: true) {
      count
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
                id
                display_label
              }
            }
          }
          roles {
            count
            edges {
              node {
                id
                display_label
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
