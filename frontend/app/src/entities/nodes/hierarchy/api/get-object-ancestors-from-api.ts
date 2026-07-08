import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export interface GetObjectAncestorsFromApiParams extends ContextParams {
  objectKind: string;
  objectId: string;
}

function getObjectAncestorsQuery({
  objectKind,
  objectId,
}: Pick<GetObjectAncestorsFromApiParams, "objectKind" | "objectId">): string {
  return jsonToGraphQLQuery({
    query: {
      __name: `Get${objectKind}Ancestors`,
      [objectKind]: {
        __args: {
          ids: [objectId],
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
  const query = getObjectAncestorsQuery({ objectKind, objectId });

  return graphqlClient.query({
    query: gql(query),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
