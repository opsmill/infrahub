import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS = gql`
  query GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS(
    $search: String
    $offset: Int
    $limit: Int
  ) {
    CoreGlobalPermission(
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
