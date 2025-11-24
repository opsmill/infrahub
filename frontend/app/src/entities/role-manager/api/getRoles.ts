import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ROLES = gql`
  query GET_ROLE_MANAGEMENT_ROLES(
    $search: String
    $offset: Int
    $limit: Int
  ) {
    CoreAccountRole(
      any__value: $search
      partial_match: true
      offset: $offset
      limit: $limit
    ) {
      count
      edges {
        node {
          id
          display_label
          hfid
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
