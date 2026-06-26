import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

/** The pool's GetResource input; the mandatory `id` is enforced at the call site. */
export interface AllocateResourceInput {
  id: string;
  /** Address mask (address pool) or subnet size (prefix pool); omitted uses the pool default. */
  prefix_length?: number;
  data?: Record<string, unknown>;
}

export interface AllocateResourceFromApiParams extends BranchContextParams {
  poolGetResourceMutationName: string;
  data: AllocateResourceInput;
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
