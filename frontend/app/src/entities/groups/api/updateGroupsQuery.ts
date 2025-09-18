import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

export const updateGroupsQuery = ({
  schema,
}: {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
}) => {
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
};
