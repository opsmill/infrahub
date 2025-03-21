import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

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
