import { gql } from "@apollo/client";

export const CREATE_ACCOUNT_TOKEN = gql`
  mutation InfrahubAccountTokenCreate($name: String!) {
    InfrahubAccountTokenCreate(data: { name: $name }) {
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
