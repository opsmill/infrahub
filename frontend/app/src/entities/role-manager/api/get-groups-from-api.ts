import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export const GET_ROLE_MANAGEMENT_GROUPS = graphql(`
  query GET_ROLE_MANAGEMENT_GROUPS($search: String, $offset: Int, $limit: Int) {
    CoreAccountGroup(any__value: $search, partial_match: true, offset: $offset, limit: $limit) {
      count
      edges {
        node {
          id
          display_label
          hfid
          name {
            value
          }
          description {
            value
          }
          label {
            value
          }
          group_type {
            value
          }
          members {
            edges {
              node {
                id
                display_label
              }
            }
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

export interface GetGroupsFromApiParams extends ContextParams, PaginationParams {
  search?: string;
}

export function getRoleManagerGroupsFromApi({
  search,
  offset,
  limit,
  branchName,
  atDate,
}: GetGroupsFromApiParams) {
  return graphqlClient.query({
    query: GET_ROLE_MANAGEMENT_GROUPS,
    variables: { search, offset, limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
