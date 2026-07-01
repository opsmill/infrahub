import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// No `scope` argument → the server resolves the default `EFFECTIVE` scope, i.e.
// each key's resolved value plus the source (USER | GLOBAL | DEFAULT) it came from.
const GET_EFFECTIVE_PREFERENCES = graphql(`
  query InfrahubPreferences {
    InfrahubPreferences {
      preferences {
        key
        value
        source
      }
      can_edit_global_preferences
    }
  }
`);

export const getEffectivePreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_EFFECTIVE_PREFERENCES,
    fetchPolicy: "network-only",
  });
};
