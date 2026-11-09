import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
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

export interface DeleteObjectsContext {
  processErrorMessage?: (message: string) => void;
}

export interface DeleteObjectsFromApiParams extends BranchContextParams {
  objects: Array<ObjectParam>;
  context: DeleteObjectsContext;
}

export function deleteObjectsFromApi({ objects, branchName, context }: DeleteObjectsFromApiParams) {
  return graphqlClient.mutate({
    mutation: graphql(getDeleteObjectsQuery(objects)),
    context: {
      branch: branchName,
      ...context,
    },
  });
}
