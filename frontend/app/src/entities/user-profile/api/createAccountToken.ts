import { gql } from "@apollo/client";

export const CREATE_ACCOUNT_TOKEN = gql`
  mutation InfrahubAccountTokenCreate($name: String!, $expiration: String) {
    InfrahubAccountTokenCreate(data: { name: $name, expiration: $expiration }) {
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
