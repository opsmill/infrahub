import { graphql, graphqlClient } from "@/shared/api/graphql/client";

// Preferences resolved user → global → default; each field carries its resolved value and source.
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
  });
};
