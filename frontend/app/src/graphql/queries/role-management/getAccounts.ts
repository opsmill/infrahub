import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_ACCOUNTS = gql`
  query {
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
