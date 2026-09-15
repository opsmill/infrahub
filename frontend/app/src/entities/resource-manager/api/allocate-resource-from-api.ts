import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { BranchContextParams } from "@/shared/api/types";

/** The pool's GetResource input; the mandatory `id` is enforced at the call site. */
export interface AllocateResourceInput {
  id: string;
  /** Address mask (address pool) or subnet size (prefix pool); omitted uses the pool default. */
  prefix_length?: number;
  /** Concrete kind to allocate from an IP address pool; omitted uses the pool default. */
  address_type?: string;
  /** Concrete kind to allocate from an IP prefix pool; omitted uses the pool default. */
  prefix_type?: string;
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
    mutation: graphql(mutation),
    context: {
      branch: branchName,
    },
  });
}
