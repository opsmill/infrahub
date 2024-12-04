import { jsonToGraphQLQuery } from "json-to-graphql-query";

export const generateRelationshipListQuery = ({
  peer,
  parent,
  peerField,
}: {
  peer: string;
  parent?: { name?: string; value?: string };
  peerField?: string;
}): string => {
  const args = parent?.value ? { __args: { [`${parent.name}__ids`]: [parent.value] } } : {};

  const request = {
    query: {
      __name: "GetRelationshipList",
      [peer]: {
        ...args,
        edges: {
          node: {
            id: true,
            display_label: true,
            ...(peerField ? { [peerField]: { value: true } } : {}),
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
