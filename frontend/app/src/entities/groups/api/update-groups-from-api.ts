import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

function buildUpdateGroupsQuery(schema: NodeSchema | ProfileSchema) {
  const request = {
    mutation: {
      __variables: {
        id: "String",
        groupIds: "[RelatedNodeInput]",
      },
      __name: `${schema.kind}UpdateGroups`,
      [`${schema.kind}Update`]: {
        __args: {
          data: {
            id: new VariableType("id"),
            member_of_groups: new VariableType("groupIds"),
          },
        },
        ok: true,
      },
    },
  };

  return gql(jsonToGraphQLQuery(request));
}

export interface UpdateGroupsFromApiParams extends ContextParams {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
  groupIds: Array<{ id: string }>;
}

export function updateGroupsFromApi({
  schema,
  objectId,
  groupIds,
  branchName,
  atDate,
}: UpdateGroupsFromApiParams) {
  const mutation = buildUpdateGroupsQuery(schema);

  return graphqlClient.mutate({
    mutation,
    variables: { id: objectId, groupIds },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
