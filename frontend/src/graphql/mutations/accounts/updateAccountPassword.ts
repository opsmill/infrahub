import { gql } from "@apollo/client";

export const UPDATE_ACCOUNT_PASSWORD = gql`
  mutation UPDATE_ACCOUNT_PASSWORD($password: String!) {
    CoreAccountSelfUpdate(data: { password: $password }) {
      ok
    }
  }
`;
