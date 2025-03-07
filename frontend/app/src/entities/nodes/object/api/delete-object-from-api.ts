import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

const getDeleteObjectQuery = (kind: string, objectid: string) => {
  const query = {
    mutation: {
      [`${kind}Delete`]: {
        __args: {
          data: { id: objectid },
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
    mutation: gql(getDeleteObjectQuery(objectKind, objectId)),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
