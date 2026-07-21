import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_GLOBAL_PREFERENCES = graphql(`
  query InfrahubGlobalPreferences {
    InfrahubGlobalPreferences {
      date_format
      timezone
    }
  }
`);

export const getGlobalPreferencesFromApi = async () => {
  return graphqlClient.query({ query: GET_GLOBAL_PREFERENCES });
};
