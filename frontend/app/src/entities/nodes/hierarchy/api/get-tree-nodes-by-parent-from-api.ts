import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export interface GetTreeNodesByParentQueryParams extends PaginationParams {
  objectKind: string;
  parentObjectId?: string | null;
}

export function GetTreeNodesByParentQuery({
  objectKind,
  parentObjectId,
  limit,
  offset,
}: GetTreeNodesByParentQueryParams) {
  return jsonToGraphQLQuery({
    query: {
      __name: `GetTreeNodesByParent_${objectKind}`,
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

export interface GetTreeNodesByParentFromApiParams
  extends GetTreeNodesByParentQueryParams,
    ContextParams {}

export function GetTreeNodesByParentFromApi({
  branchName,
  atDate,
  ...params
}: GetTreeNodesByParentFromApiParams) {
  return graphqlClient.query({
    query: graphql(GetTreeNodesByParentQuery(params)),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
