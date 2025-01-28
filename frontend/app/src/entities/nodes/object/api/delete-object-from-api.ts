import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
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
}: { objectKind: string; objectId: string; branchName: string; atDate: Date | null }) {
  return graphqlClient.mutate({
    mutation: gql(getDeleteObjectQuery(objectKind, objectId)),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
