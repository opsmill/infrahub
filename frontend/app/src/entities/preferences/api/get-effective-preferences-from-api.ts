import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// Caller's resolved preferences (user → global → default). Each field carries the resolved
// value plus the source (USER | GLOBAL | DEFAULT) it came from.
const GET_EFFECTIVE_PREFERENCES = graphql(`
  query InfrahubEffectivePreferences {
    InfrahubEffectivePreferences {
      date_format {
        value
        source
      }
      timezone {
        value
        source
      }
    }
  }
`);

export const getEffectivePreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_EFFECTIVE_PREFERENCES,
    fetchPolicy: "network-only",
  });
};
