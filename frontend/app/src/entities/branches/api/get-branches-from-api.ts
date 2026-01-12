import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { PaginationParams } from "@/shared/api/types";
import type { Filter } from "@/shared/hooks/useFilters";

export const BRANCHES_PER_PAGE = 40;

export interface GetBranchesFromApiParams extends PaginationParams {
  filters?: Filter[];
}

export const getBranchesFromApi = async ({
  filters,
  limit = BRANCHES_PER_PAGE,
  offset,
}: GetBranchesFromApiParams = {}) => {
  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetBranches",
      InfrahubBranch: {
        __args: {
          limit,
          ...(offset !== undefined && { offset }),
          ...(filters ? addFiltersToRequest(filters) : {}),
        },
        edges: {
          node: {
            id: true,
            name: { value: true },
            description: { value: true },
            origin_branch: { value: true },
            branched_from: { value: true },
            status: { value: true },
            created_at: true,
            sync_with_git: { value: true },
            is_default: { value: true },
            has_schema_changes: { value: true },
          },
          node_metadata: {
            created_at: true,
            created_by: {
              id: true,
              display_label: true,
              hfid: true,
              __typename: true,
            },
            updated_at: true,
            updated_by: {
              id: true,
              display_label: true,
              hfid: true,
              __typename: true,
            },
          },
        },
      },
    },
  });

  const query = gql(queryString);
  return graphqlClient.query({ query });
};
