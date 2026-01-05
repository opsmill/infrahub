import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const query = gql`
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
`;

export const getAccountTokenFromApi = async () => {
  return graphqlClient.query({ query });
};
