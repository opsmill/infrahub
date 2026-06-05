import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";

export const getRelationshipParent = ({ kind, attribute }: { kind: string; attribute: string }) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getRelationshipParent__${kind}`,
      __variables: { ids: "[ID]" },
      [kind]: {
        __args: { [attribute]: new VariableType("ids") },
        count: true,
        edges: {
          node: nodeCoreFragment,
        },
      },
    },
  });
};
