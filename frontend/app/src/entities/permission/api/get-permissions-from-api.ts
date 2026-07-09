import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

export type GetPermissionsFromApiParams = ContextParams & { kind: string };

const getObjectPermissionsQuery = (kind: string) => {
  const request = {
    query: {
      __name: `getObjectPermissions_${kind}`,
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

export const getPermissionsFromApi = ({
  kind,
  branchName,
  atDate,
}: GetPermissionsFromApiParams) => {
  const query = gql(getObjectPermissionsQuery(kind));
  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
