import { jsonToGraphQLQuery } from "json-to-graphql-query";

export const getObjectPermissionsQuery = (kind: string) => {
  const request = {
    query: {
      __name: "getObjectPermissions",
      [kind]: {
        permissions: {
          edges: {
            node: {
              kind: true,
              view: true,
              create: true,
              update: true,
              delete: true,
            },
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
