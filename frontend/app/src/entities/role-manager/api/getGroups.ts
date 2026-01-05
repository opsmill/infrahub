import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_GROUPS = gql`
  query GET_ROLE_MANAGEMENT_GROUPS(
    $search: String
    $offset: Int
    $limit: Int
  ) {
    CoreAccountGroup(
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
          description {
            value
          }
          label {
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
