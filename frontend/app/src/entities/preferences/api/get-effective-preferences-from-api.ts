import { graphql, graphqlClient } from "@/shared/api/graphql/client";

// Each field carries its resolved value and source plus the layer it would fall back to, so a
// client can preview clearing an override.
const GET_EFFECTIVE_PREFERENCES = graphql(`
  query InfrahubEffectivePreferences {
    InfrahubEffectivePreferences {
      date_format {
        value
        source
        inherited
      }
      timezone {
        value
        source
        inherited
      }
    }
  }
`);

export const getEffectivePreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_EFFECTIVE_PREFERENCES,
  });
};
