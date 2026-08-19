import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams, PaginationParams } from "@/shared/api/types";

export interface GetTreeNodesByParentQueryParams extends PaginationParams {
  objectKind: string;
  parentObjectId?: string | null;
}

export function GetTreeNodesByParentQuery({
  objectKind,
  parentObjectId,
}: Omit<GetTreeNodesByParentQueryParams, "limit" | "offset">) {
  return jsonToGraphQLQuery({
    query: {
      __name: `GetTreeNodesByParent_${objectKind}`,
      __variables: {
        limit: "Int",
        offset: "Int",
        ...(parentObjectId ? { parentIds: "[ID]" } : {}),
      },
      [objectKind]: {
        __args: {
          limit: new VariableType("limit"),
          offset: new VariableType("offset"),
          ...(parentObjectId
            ? { parent__ids: new VariableType("parentIds") }
            : { parent__isnull: true }),
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
  limit,
  offset,
  ...params
}: GetTreeNodesByParentFromApiParams) {
  return graphqlClient.query({
    query: gql(GetTreeNodesByParentQuery(params)),
    variables: {
      limit,
      offset,
      ...(params.parentObjectId ? { parentIds: [params.parentObjectId] } : {}),
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
