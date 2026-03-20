import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export const GET_ROLE_MANAGEMENT_ROLES = graphql(`
  query GET_ROLE_MANAGEMENT_ROLES($search: String, $offset: Int, $limit: Int) {
    CoreAccountRole(any__value: $search, partial_match: true, offset: $offset, limit: $limit) {
      count
      edges {
        node {
          id
          display_label
          hfid
          name {
            value
          }
          groups {
            count
            edges {
              node {
                id
                display_label
              }
            }
          }
          permissions {
            count
            edges {
              node {
                id
                display_label
                identifier {
                  value
                }
              }
            }
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

export interface GetRolesFromApiParams extends ContextParams, PaginationParams {
  search?: string;
}

export function getRolesFromApi({
  search,
  offset,
  limit,
  branchName,
  atDate,
}: GetRolesFromApiParams) {
  return graphqlClient.query({
    query: GET_ROLE_MANAGEMENT_ROLES,
    variables: { search, offset, limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
