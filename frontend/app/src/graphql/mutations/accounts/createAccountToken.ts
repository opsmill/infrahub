import { gql } from "@apollo/client";

export const CREATE_ACCOUNT_TOKEN = gql`
  mutation CoreAccountTokenCreate($name: String!) {
    CoreAccountTokenCreate(data: { name: $name }) {
      object {
        id
        token {
          value
        }
      }
      ok
    }
  }
`;
