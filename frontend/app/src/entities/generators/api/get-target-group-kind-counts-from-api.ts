import { jsonToGraphQLQuery } from "json-to-graphql-query";

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
  const fields = Object.fromEntries(
    groupIds.map((groupId, index) => [
      `${TARGET_GROUP_ALIAS_PREFIX}${index}`,
      {
        __aliasFor: nodeKind,
        __args: { member_of_groups__ids: [groupId] },
        count: true,
      },
    ])
  );

  const query = graphql(
    jsonToGraphQLQuery({
      query: {
        __name: "GetTargetGroupKindCounts",
        ...fields,
      },
    })
  );

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
      // A failed read only means no generator can be offered, which is not worth an error toast.
      processErrorMessage: () => {},
    },
  });
};
