import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

export const TARGET_GROUP_ALIAS_PREFIX = "group";

export interface GetTargetGroupKindCountsFromApiParams extends ContextParams {
  nodeKind: string;
  groupIds: string[];
}

export const getTargetGroupKindCountsFromApi = async ({
  nodeKind,
  groupIds,
  branchName,
  atDate,
}: GetTargetGroupKindCountsFromApiParams) => {
  const aliasedGroupIds = groupIds.map((groupId, index) => ({
    alias: `${TARGET_GROUP_ALIAS_PREFIX}${index}`,
    variable: `${TARGET_GROUP_ALIAS_PREFIX}${index}Ids`,
    groupId,
  }));

  const query = graphql(
    jsonToGraphQLQuery({
      query: {
        __name: "GetTargetGroupKindCounts",
        __variables: Object.fromEntries(aliasedGroupIds.map(({ variable }) => [variable, "[ID]"])),
        ...Object.fromEntries(
          aliasedGroupIds.map(({ alias, variable }) => [
            alias,
            {
              __aliasFor: nodeKind,
              __args: { member_of_groups__ids: new VariableType(variable) },
              count: true,
            },
          ])
        ),
      },
    })
  );

  return graphqlClient.query({
    query,
    variables: Object.fromEntries(
      aliasedGroupIds.map(({ variable, groupId }) => [variable, [groupId]])
    ),
    context: {
      branch: branchName,
      date: atDate,
      // A failed read only means no generator can be offered, which is not worth an error toast.
      processErrorMessage: () => {},
    },
  });
};
