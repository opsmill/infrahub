import { gql } from "@apollo/client";

export const GET_ALL_ACCOUNTS = gql`
  query GetAllAccounts {
    CoreGenericAccount {
      edges {
        node {
          id
          display_label
        }
      }
    }
  }
`;
