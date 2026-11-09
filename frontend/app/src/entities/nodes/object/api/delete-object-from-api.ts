import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

const getDeleteObjectQuery = (kind: string, objectId: string) => {
  const query = {
    mutation: {
      [`${kind}Delete`]: {
        __args: {
          data: { id: objectId },
        },
        ok: true,
      },
    },
  };

  return jsonToGraphQLQuery(query);
};

export function deleteObjectFromApi({
  objectKind,
  objectId,
  branchName,
  atDate,
}: ContextParams & { objectKind: string; objectId: string }) {
  return graphqlClient.mutate({
    mutation: graphql(getDeleteObjectQuery(objectKind, objectId)),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
