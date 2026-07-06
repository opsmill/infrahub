import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// The caller's account-wide (non-object) permissions. Each edge carries the
// permission `action` (e.g. "manage_global_preferences") and the `decision` the
// backend resolved for the caller.
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
