import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// `scope: GLOBAL` returns the organisation's OWN raw values (every entry has
// source=GLOBAL), never merged with the caller's personal overrides. The server
// gates this on `manage_global_preferences`.
const GET_GLOBAL_PREFERENCES = graphql(`
  query InfrahubGlobalPreferences {
    InfrahubPreferences(scope: GLOBAL) {
      preferences {
        key
        value
        source
      }
    }
  }
`);

export const getGlobalPreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_GLOBAL_PREFERENCES,
    fetchPolicy: "network-only",
  });
};
