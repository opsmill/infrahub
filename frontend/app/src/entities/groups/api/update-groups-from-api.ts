import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

function buildUpdateGroupsMutation(objectKind: string) {
  return gql(
    jsonToGraphQLQuery({
      mutation: {
        __variables: {
          id: "String",
          groupIds: "[RelatedNodeInput]",
        },
        __name: `${objectKind}UpdateGroups`,
        [`${objectKind}Update`]: {
          __args: {
            data: {
              id: new VariableType("id"),
              member_of_groups: new VariableType("groupIds"),
            },
          },
          ok: true,
        },
      },
    })
  );
}

export interface UpdateGroupsFromApiParams extends ContextParams {
  objectKind: string;
  objectId: string;
  groupIds: Array<{ id: string }>;
}

export function updateGroupsFromApi({
  objectKind,
  objectId,
  groupIds,
  branchName,
  atDate,
}: UpdateGroupsFromApiParams) {
  return graphqlClient.mutate({
    mutation: buildUpdateGroupsMutation(objectKind),
    variables: { id: objectId, groupIds },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
