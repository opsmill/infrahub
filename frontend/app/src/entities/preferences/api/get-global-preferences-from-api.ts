import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// The organisation's OWN raw values, never merged with the caller's personal
// overrides (each field is null when nothing is stored). The server gates this
// on `manage_global_preferences`.
const GET_GLOBAL_PREFERENCES = graphql(`
  query InfrahubGlobalPreferences {
    InfrahubGlobalPreferences {
      date_format
      timezone
    }
  }
`);

export const getGlobalPreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_GLOBAL_PREFERENCES,
    fetchPolicy: "network-only",
  });
};
