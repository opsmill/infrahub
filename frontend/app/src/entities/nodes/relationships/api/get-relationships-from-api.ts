import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import {
  type GenerateRelationshipListQueryParams,
  generateRelationshipListQuery,
  isIdFilter,
} from "@/entities/nodes/relationships/api/generate-relationship-list.query";

export type getRelationshipsFromApiParams = ContextParams & GenerateRelationshipListQueryParams;

export const getRelationshipsFromApi = async ({
  peer,
  limit,
  offset,
  search,
  branchName,
  atDate,
  filterQuery,
}: getRelationshipsFromApiParams) => {
  const query = gql(generateRelationshipListQuery({ peer, filterQuery }));

  const idFilterVariables = Object.fromEntries(
    Object.entries(filterQuery ?? {}).filter(([filterName]) => isIdFilter(filterName))
  );

  return graphqlClient.query({
    query,
    variables: { limit, offset, search, ...idFilterVariables },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
