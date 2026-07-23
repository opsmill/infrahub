import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

export interface GetObjectAncestorsFromApiParams extends ContextParams {
  objectKind: string;
  objectId: string;
}

function getObjectAncestorsQuery({
  objectKind,
}: Pick<GetObjectAncestorsFromApiParams, "objectKind">): string {
  return jsonToGraphQLQuery({
    query: {
      __name: `Get${objectKind}Ancestors`,
      __variables: {
        ids: "[ID]",
      },
      [objectKind]: {
        __args: {
          ids: new VariableType("ids"),
        },
        edges: {
          node: {
            id: true,
            hfid: true,
            display_label: true,
            __typename: true,
            parent: {
              node: {
                id: true,
                hfid: true,
                display_label: true,
                __typename: true,
              },
            },
            ancestors: {
              edges: {
                node: {
                  id: true,
                  hfid: true,
                  display_label: true,
                  __typename: true,
                  parent: {
                    node: {
                      id: true,
                      hfid: true,
                      display_label: true,
                      __typename: true,
                    },
                  },
                },
              },
            },
          },
        },
      },
    },
  });
}

export const getObjectAncestorsFromApi = async ({
  objectKind,
  objectId,
  branchName,
  atDate,
}: GetObjectAncestorsFromApiParams) => {
  const query = getObjectAncestorsQuery({ objectKind });

  return graphqlClient.query({
    query: graphql(query),
    variables: { ids: [objectId] },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
