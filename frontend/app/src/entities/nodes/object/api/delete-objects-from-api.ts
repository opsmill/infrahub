import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { generateRandomString } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

const getDeleteObjectsQuery = (kind: string, objectids: Array<string>) => {
  // Creates dynamic mutations wwith aliases
  const mutations = objectids.reduce((acc, objectid) => {
    return {
      ...acc,
      // Alias key must be a string without numbers
      [generateRandomString()]: {
        __aliasFor: `${kind}Delete`,
        __args: {
          data: { id: objectid },
        },
        ok: true,
      },
    };
  }, {});

  const query = {
    mutation: mutations,
  };

  return jsonToGraphQLQuery(query);
};

export function deleteObjectsFromApi({
  objectKind,
  objectIds,
  branchName,
  atDate,
}: ContextParams & { objectKind: string; objectIds: Array<string> }) {
  return graphqlClient.mutate({
    mutation: gql(getDeleteObjectsQuery(objectKind, objectIds)),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
