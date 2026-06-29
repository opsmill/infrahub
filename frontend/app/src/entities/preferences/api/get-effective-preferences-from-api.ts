import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_EFFECTIVE_PREFERENCES = graphql(`
  query GetEffectivePreferences {
    InfrahubEffectivePreferences {
      date_format
      timezone
      user_date_format
      user_timezone
      global_date_format
      global_timezone
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
