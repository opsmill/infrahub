import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const CREATE_ACCOUNT_TOKEN = graphql(`
  mutation InfrahubAccountTokenCreate($tokenName: String!, $tokenExpirationDate: String) {
    InfrahubAccountTokenCreate(data: { name: $tokenName, expiration: $tokenExpirationDate }) {
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

export interface CreateAccountTokenFromApiParams extends VariablesOf<typeof CREATE_ACCOUNT_TOKEN> {}

export function createAccountTokenFromApi({
  tokenName,
  tokenExpirationDate,
}: CreateAccountTokenFromApiParams) {
  return graphqlClient.mutate({
    mutation: CREATE_ACCOUNT_TOKEN,
    variables: {
      tokenName,
      tokenExpirationDate,
    },
  });
}
