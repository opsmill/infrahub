import { graphql, graphqlClient } from "@/shared/api/graphql/client";

// Each field carries its resolved value and source plus the layer it would fall back to, so a
// client can preview clearing an override without a second round trip.
const GET_EFFECTIVE_PREFERENCES = graphql(`
  query InfrahubEffectivePreferences {
    InfrahubEffectivePreferences {
      date_format {
        value
        source
        inherited {
          value
          source
        }
      }
      timezone {
        value
        source
        inherited {
          value
          source
        }
      }
    }
  }
`);

export const getEffectivePreferencesFromApi = async () => {
  return graphqlClient.query({
    query: GET_EFFECTIVE_PREFERENCES,
  });
};
