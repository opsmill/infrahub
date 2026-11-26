import { graphql, graphqlClient } from "@/shared/api/graphql/client";

const GET_GLOBAL_PREFERENCES = graphql(`
  query InfrahubGlobalPreferences {
    InfrahubGlobalPreferences {
      date_format
      timezone
      instance_label
      instance_color
    }
  }
`);

export const getGlobalPreferencesFromApi = async () => {
  return graphqlClient.query({ query: GET_GLOBAL_PREFERENCES });
};
