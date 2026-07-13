import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_GLOBAL_PERMISSIONS = graphql(`
  query InfrahubGlobalPermissions {
    InfrahubPermissions {
      global_permissions {
        edges {
          node {
            action
            decision
          }
        }
      }
    }
  }
`);

export const getGlobalPermissionsFromApi = async () => {
  return graphqlClient.query({ query: GET_GLOBAL_PERMISSIONS });
};
