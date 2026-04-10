import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

const getObjectGroups = ({ objectKind }: { objectKind: string }) => {
  return jsonToGraphQLQuery({
    query: {
      __name: `getObjectGroups__${objectKind}`,
      __variables: { ids: "[ID]" },
      [objectKind]: {
        __args: { ids: new VariableType("ids") },
        edges: {
          node: {
            member_of_groups: {
              count: true,
              edges: {
                node: {
                  id: true,
                  display_label: true,
                  description: { value: true },
                  group_type: { value: true },
                  members: { count: true },
                },
              },
            },
          },
        },
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
  });
};

export interface GetGroupsFromApiParams extends ContextParams {
  objectKind: string;
  objectId: string;
}

export function getGroupsFromApi({
  objectKind,
  objectId,
  branchName,
  atDate,
}: GetGroupsFromApiParams) {
  const query = gql(getObjectGroups({ objectKind }));

  return graphqlClient.query({
    query,
    variables: { ids: [objectId] },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
