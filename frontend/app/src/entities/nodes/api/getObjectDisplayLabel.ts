import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

export const getObjectDisplayLabel = ({
  kind,
  peerField,
}: {
  kind: string;
  peerField?: string;
}) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getObjectDisplayLabel__${kind}`,
      __variables: { ids: "[ID]" },
      [kind]: {
        __args: { ids: new VariableType("ids") },
        edges: {
          node: {
            id: true,
            display_label: true,
            ...(peerField ? { [peerField]: { value: true } } : {}),
          },
        },
      },
    },
  });
};
