import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// The caller's resolved preferences (user → global → default). Each field is a
// typed, self-describing object carrying the resolved value plus the source
// (USER | GLOBAL | DEFAULT) it was resolved from.
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
