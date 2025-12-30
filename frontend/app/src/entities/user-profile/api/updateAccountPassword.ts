import { graphql } from "gql.tada";

export const UPDATE_ACCOUNT_PASSWORD = graphql(`
  mutation UPDATE_ACCOUNT_PASSWORD($password: String!) {
    InfrahubAccountSelfUpdate(data: { password: $password }) {
      ok
    }
  }
`);
