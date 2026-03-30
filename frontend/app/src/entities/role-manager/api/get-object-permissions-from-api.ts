import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export const GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS = graphql(`
  query GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS($search: String, $offset: Int, $limit: Int) {
    CoreObjectPermission(any__value: $search, partial_match: true, offset: $offset, limit: $limit) {
      count
      edges {
        node {
          id
          display_label
          hfid
          name {
            value
          }
          namespace {
            value
          }
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

export interface GetObjectPermissionsFromApiParams extends ContextParams, PaginationParams {
  search?: string;
}

export function getObjectPermissionsFromApi({
  search,
  offset,
  limit,
  branchName,
  atDate,
}: GetObjectPermissionsFromApiParams) {
  return graphqlClient.query({
    query: GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS,
    variables: { search, offset, limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
