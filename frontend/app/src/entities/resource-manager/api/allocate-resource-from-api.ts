import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface AllocateResourceFromApiParams extends BranchContextParams {
  poolGetResourceMutationName: string;
  /**
   * The pool's GetResource input, built by the caller: `{ id, prefix_length?, data? }`.
   * Mirrors createObjectFromApi/updateObjectFromApi, where the api wraps a caller-built
   * `data` rather than owning individual fields.
   */
  data: Record<string, unknown>;
}

export function allocateResourceFromApi({
  poolGetResourceMutationName,
  data,
  branchName,
}: AllocateResourceFromApiParams) {
  const mutation = jsonToGraphQLQuery({
    mutation: {
      [poolGetResourceMutationName]: {
        __args: {
          data,
        },
        node: {
          id: true,
          kind: true,
          display_label: true,
        },
      },
    },
  });

  return graphqlClient.mutate({
    mutation: gql(mutation),
    context: {
      branch: branchName,
    },
  });
}
