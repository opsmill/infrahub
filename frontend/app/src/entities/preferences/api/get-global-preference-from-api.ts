import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_GLOBAL_PREFERENCE = graphql(`
  query GetGlobalPreference {
    CoreGlobalPreference {
      edges {
        node {
          id
          date_format {
            value
          }
          timezone {
            value
          }
        }
      }
    }
  }
`);

export const getGlobalPreferenceFromApi = async () => {
  return graphqlClient.query({
    query: GET_GLOBAL_PREFERENCE,
    fetchPolicy: "network-only",
  });
};
