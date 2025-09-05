import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";

import {
  GenerateRelationshipListQueryParams,
  generateRelationshipListQuery,
} from "@/entities/nodes/api/generateRelationshipListQuery";

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
  const query = gql(generateRelationshipListQuery({ peer, limit, offset, search, filterQuery }));

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
