import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import {
  type GenerateRelationshipListQueryParams,
  generateRelationshipListQuery,
} from "@/entities/nodes/relationships/api/generate-relationship-list.query";

export type getRelationshipsFromApiParams = ContextParams &
  Omit<GenerateRelationshipListQueryParams, "parent">;

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

  return graphqlClient.query({
    query,
    variables: { limit, offset, search },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
