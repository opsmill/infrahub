import { jsonToGraphQLQuery } from "json-to-graphql-query";

export const generateRelationshipListQuery = ({
  peer,
  parent,
  limit = 0,
  offset = 0,
}: {
  peer: string;
  parent?: { name?: string; value?: string };
  limit?: number;
  offset?: number;
}): string => {
  const defaultArgs = { limit, offset };

  const args = parent?.value
    ? { ...defaultArgs, [`${parent.name}__ids`]: [parent.value] }
    : { ...defaultArgs };

  const request = {
    query: {
      __name: "GetRelationshipList",
      [peer]: {
        __args: {
          ...args,
        },
        count: true,
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
