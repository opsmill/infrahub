import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

/**
 * The pool's GetResource input. Typed so the mandatory pool `id` is enforced at the call
 * site (a bare `{}` won't compile), while the optional allocation fields stay part of the
 * same caller-built object rather than separate ad-hoc params.
 */
export interface AllocateResourceInput {
  /** ID of the pool to allocate from. */
  id: string;
  /**
   * Prefix length to allocate with — the new address's mask for an IP address pool, or the
   * carved-out subnet size for an IP prefix pool. Omitted to use the pool's default.
   */
  prefix_length?: number;
  /** Additional attributes for the newly created node. */
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
