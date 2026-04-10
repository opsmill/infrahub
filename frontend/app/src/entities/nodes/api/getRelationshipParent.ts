import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

export const getRelationshipParent = ({ kind, attribute }: { kind: string; attribute: string }) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getRelationshipParent__${kind}`,
      __variables: { ids: "[ID]" },
      [kind]: {
        __args: { [attribute]: new VariableType("ids") },
        count: true,
        edges: {
          node: {
            id: true,
            display_label: true,
          },
        },
      },
    },
  });
};
