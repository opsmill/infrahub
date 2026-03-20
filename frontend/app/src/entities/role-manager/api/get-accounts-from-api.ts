import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export const GET_ROLE_MANAGEMENT_ACCOUNTS = graphql(`
  query GET_ROLE_MANAGEMENT_ACCOUNTS($search: String, $offset: Int, $limit: Int) {
    CoreGenericAccount(any__value: $search, partial_match: true, offset: $offset, limit: $limit) {
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
          account_type {
            value
          }
          status {
            value
            color
            description
          }
          member_of_groups {
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

export interface GetAccountsFromApiParams extends ContextParams, PaginationParams {
  search?: string;
}

export function getAccountsFromApi({
  search,
  offset,
  limit,
  branchName,
  atDate,
}: GetAccountsFromApiParams) {
  return graphqlClient.query({
    query: GET_ROLE_MANAGEMENT_ACCOUNTS,
    variables: { search, offset, limit },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
