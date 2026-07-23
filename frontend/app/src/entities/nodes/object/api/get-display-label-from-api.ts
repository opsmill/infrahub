import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const getNodeLabelQuery = ({ hasObjectId, kind }: { hasObjectId: boolean; kind: string }) => {
  const request = {
    query: {
      __name: "GET_DISPLAY_LABEL",
      ...(hasObjectId ? { __variables: { ids: "[ID]" } } : {}),
      [kind]: {
        __args: {
          ...(hasObjectId ? { ids: new VariableType("ids") } : {}),
        },
        edges: {
          node: {
            display_label: true,
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};

export function getNodeLabelFromApi({
  objectId,
  kind,
  branchName,
  atDate,
}: {
  objectId?: string | null;
  kind: string;
} & ContextParams) {
  return graphqlClient.query({
    query: gql(getNodeLabelQuery({ hasObjectId: Boolean(objectId), kind })),
    ...(objectId ? { variables: { ids: [objectId] } } : {}),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
