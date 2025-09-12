import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

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
