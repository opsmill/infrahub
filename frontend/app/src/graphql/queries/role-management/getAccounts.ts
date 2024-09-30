import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ACCOUNTS = gql`
  query GET_ROLE_MANAGEMENT_ACCOUNTS {
    CoreAccount {
      count
      edges {
        node {
          id
          description {
            value
          }
          display_label
          account_type {
            value
          }
          status {
            value
          }
        }
      }
    }
  }
`;
