import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const query = graphql(`
  query InfrahubAccountToken {
    InfrahubAccountToken {
      count
      edges {
        node {
          id
          name
          expiration
        }
      }
    }
  }
`);

export const getAccountTokenFromApi = async () => {
  return graphqlClient.query({ query });
};
