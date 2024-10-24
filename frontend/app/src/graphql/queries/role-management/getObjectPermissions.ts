import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS = gql`
  query GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS($search: String) {
    CoreObjectPermission(any__value: $search, partial_match: true) {
      count
      edges {
        node {
          id
          display_label
          name {
            value
          }
          namespace {
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
                display_label
              }
            }
          }
          identifier {
            value
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
