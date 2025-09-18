import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface ObjectParam {
  id: string;
  kind: string;
}

const getDeleteObjectsQuery = (objects: Array<ObjectParam>) => {
  // Creates dynamic mutations with aliases
  const mutations = objects.reduce((acc, { id, kind }, index) => {
    return {
      ...acc,
      [`delete_${kind}_${index}`]: {
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

export interface DeleteObjectsFromApiParams extends BranchContextParams {
  objects: Array<ObjectParam>;
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
