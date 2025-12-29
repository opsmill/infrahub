import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import {
  type GetObjectAncestorsQueryParams,
  getObjectAncestorsQuery,
} from "@/entities/nodes/hierarchy/api/query/get-object-ancestors-query";

export interface GetObjectAncestorsFromApiParams
  extends GetObjectAncestorsQueryParams,
    ContextParams {}

export const getObjectAncestorsFromApi = async ({
  objectKind,
  objectId,
  branchName,
  atDate,
}: GetObjectAncestorsFromApiParams) => {
  const query = getObjectAncestorsQuery({ objectKind, objectId });

  return graphqlClient.query({
    query: gql(query),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
