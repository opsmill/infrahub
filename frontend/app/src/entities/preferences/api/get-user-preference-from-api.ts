import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_USER_PREFERENCE = graphql(`
  query GetUserPreference($accountIds: [ID]) {
    CoreUserPreference(account__ids: $accountIds) {
      edges {
        node {
          id
          date_format {
            value
          }
          timezone {
            value
          }
        }
      }
    }
  }
`);

export interface GetUserPreferenceFromApiParams {
  accountId: string;
}

export const getUserPreferenceFromApi = async ({ accountId }: GetUserPreferenceFromApiParams) => {
  return graphqlClient.query({
    query: GET_USER_PREFERENCE,
    variables: { accountIds: [accountId] },
    fetchPolicy: "network-only",
  });
};
