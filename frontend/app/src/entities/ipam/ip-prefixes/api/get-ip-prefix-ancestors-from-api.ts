import { jsonToGraphQLQuery } from "json-to-graphql-query";

export function buildGetAncestorsQuery(objectKind: string, objectId: string): string {
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
                    node: { id: true },
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
