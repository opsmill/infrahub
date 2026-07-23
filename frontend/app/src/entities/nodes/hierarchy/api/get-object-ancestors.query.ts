import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

export type GetObjectAncestorsQueryParams = {
  objectKind: string;
  objectId: string;
};

export function getObjectAncestorsQuery({
  objectKind,
}: Omit<GetObjectAncestorsQueryParams, "objectId">): string {
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
