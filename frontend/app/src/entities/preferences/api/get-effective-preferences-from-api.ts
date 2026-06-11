import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_EFFECTIVE_PREFERENCES = graphql(`
  query GetEffectivePreferences {
    InfrahubEffectivePreferences {
      date_format
      timezone
    }
  }
`);

export const getEffectivePreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_EFFECTIVE_PREFERENCES,
    fetchPolicy: "network-only",
  });
};
