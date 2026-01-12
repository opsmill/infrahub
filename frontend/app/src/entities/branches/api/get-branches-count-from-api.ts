import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addFiltersToRequest } from "@/shared/api/graphql/utils";
import type { Filter } from "@/shared/hooks/useFilters";

export interface GetBranchesCountFromApiParams {
  filters?: Filter[];
}

export const getBranchesCountFromApi = async ({ filters }: GetBranchesCountFromApiParams = {}) => {
  const queryString = jsonToGraphQLQuery({
    query: {
      __name: "GetBranchesCount",
      InfrahubBranch: {
        __args: {
          ...(filters ? addFiltersToRequest(filters) : {}),
        },
        count: true,
      },
    },
  });

  const query = gql(queryString);
  return graphqlClient.query({ query });
};
