import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export const GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS = graphql(`
  query GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS($search: String, $offset: Int, $limit: Int) {
    CoreGlobalPermission(any__value: $search, partial_match: true, offset: $offset, limit: $limit) {
      count
      edges {
        node {
          id
          display_label
          hfid
          action {
            value
          }
          decision {
            value
          }
          roles {
            count
            edges {
              node {
                id
                display_label
              }
            }
          }
          identifier {
            value
          }
          __typename
        }
      }
      permissions {
        edges {
          node {
            kind
            view
            create
            update
            delete
          }
        }
      }
    }
  }
`);

export interface GetGlobalPermissionsFromApiParams extends ContextParams, PaginationParams {
  search?: string;
}

export function getGlobalPermissionsFromApi({
  search,
  offset,
  limit,
  branchName,
  atDate,
}: GetGlobalPermissionsFromApiParams) {
  return graphqlClient.query({
    query: GET_ROLE_MANAGEMENT_GLOBAL_PERMISSIONS,
    variables: { search, offset, limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
