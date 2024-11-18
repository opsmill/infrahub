import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ACCOUNTS = gql`
  query GET_ROLE_MANAGEMENT_ACCOUNTS($search: String) {
    CoreGenericAccount(any__value: $search, partial_match: true)  {
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
          account_type {
            value
          }
          status {
            value
            color
            description
          }
          member_of_groups {
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
