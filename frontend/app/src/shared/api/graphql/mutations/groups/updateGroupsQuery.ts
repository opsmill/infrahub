import { IProfileSchema, iNodeSchema } from "@/state/atoms/schema.atom";
import { gql } from "@apollo/client";
import { VariableType, jsonToGraphQLQuery } from "json-to-graphql-query";

export const updateGroupsQuery = ({
  schema,
}: {
  schema: iNodeSchema | IProfileSchema;
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
