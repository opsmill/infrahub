import { jsonToGraphQLQuery } from "json-to-graphql-query";

export const generateRelationshipListQuery = ({
  peer,
  parent,
}: {
  peer: string;
  parent?: { name?: string; value?: string };
}): string => {
  const args = parent?.value ? { [`${parent.name}__ids`]: [parent.value] } : {};

  const request = {
    query: {
      __name: "GetRelationshipList",
      [peer]: {
        __args: {
          ...args,
        },
        edges: {
          node: {
            id: true,
            display_label: true,
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
