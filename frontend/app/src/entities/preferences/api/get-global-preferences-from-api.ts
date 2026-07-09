import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// Organisation's OWN raw values, never merged with personal overrides (null when unset).
// Server-gated on `manage_global_preferences`.
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
