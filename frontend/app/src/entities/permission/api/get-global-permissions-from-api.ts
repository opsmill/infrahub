import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// Caller's account-wide permissions: each edge pairs an `action` with the backend-resolved `decision`.
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
  return graphqlClient.query({
    query: GET_GLOBAL_PERMISSIONS,
    fetchPolicy: "network-only",
  });
};
