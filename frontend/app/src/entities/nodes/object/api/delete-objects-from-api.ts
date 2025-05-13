import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { generateRandomString } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export interface ObjectParam {
  id: string;
  kind: string;
}

const getDeleteObjectsQuery = (objects: Array<ObjectParam>) => {
  // Creates dynamic mutations with aliases
  const mutations = objects.reduce((acc, { id, kind }) => {
    return {
      ...acc,
      // Alias key must be a string without numbers
      [generateRandomString()]: {
        __aliasFor: `${kind}Delete`,
        __args: {
          data: { id },
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

export interface DeleteObjectsFromApiParams {
  objects: Array<ObjectParam>;
  branchName: Pick<ContextParams, "branchName">;
  context: Record<string, any>;
}

export function deleteObjectsFromApi({ objects, branchName, context }: DeleteObjectsFromApiParams) {
  return graphqlClient.mutate({
    mutation: gql(getDeleteObjectsQuery(objects)),
    context: {
      branch: branchName,
      ...context,
    },
  });
}
