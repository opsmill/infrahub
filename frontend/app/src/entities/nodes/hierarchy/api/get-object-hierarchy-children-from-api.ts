import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export interface GetObjectHierarchyChildrenQueryParams extends PaginationParams {
  objectKind: string;
  parentObjectId?: string | null;
}

export function getObjectHierarchyChildrenQuery({
  objectKind,
  parentObjectId,
  limit,
  offset,
}: GetObjectHierarchyChildrenQueryParams) {
  return jsonToGraphQLQuery({
    query: {
      __name: `GetObjectChildren_${objectKind}`,
      [objectKind]: {
        __args: {
          limit,
          offset,
          ...(parentObjectId ? { parent__ids: parentObjectId } : { parent__isnull: true }),
        },
        edges: {
          node: {
            id: true,
            display_label: true,
            hfid: true,
            children: {
              count: true,
            },
          },
        },
      },
    },
  });
}

export interface GetObjectHierarchyChildrenFromApiParams
  extends GetObjectHierarchyChildrenQueryParams,
    ContextParams {}

export function getObjectHierarchyChildrenFromApi({
  branchName,
  atDate,
  ...params
}: GetObjectHierarchyChildrenFromApiParams) {
  return graphqlClient.query({
    query: gql(getObjectHierarchyChildrenQuery(params)),
    context: {
      branchName,
      atDate,
    },
  });
}
