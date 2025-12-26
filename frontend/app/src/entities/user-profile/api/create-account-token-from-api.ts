import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const CREATE_ACCOUNT_TOKEN = graphql(`
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
`);

export interface CreateAccountTokenFromApiParams {
  tokenName: string;
  tokenExpirationDate: string | null | undefined;
}

export function createAccountTokenFromApi({
  tokenName,
  tokenExpirationDate,
}: CreateAccountTokenFromApiParams) {
  return graphqlClient.mutate({
    mutation: CREATE_ACCOUNT_TOKEN,
    variables: {
      name: tokenName,
      expiration: tokenExpirationDate,
    },
  });
}
