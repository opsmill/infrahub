import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface AllocateResourceFromApiParams extends BranchContextParams {
  poolGetResourceMutationName: string;
  poolId: string;
  data: Record<string, unknown>;
  /**
   * Optional prefix length to allocate with. For an IP address pool it sets the new
   * address's mask; for an IP prefix pool it sets the size of the carved-out subnet.
   * Omitted when blank so the pool's default applies.
   */
  prefixLength?: number | null;
}

export function allocateResourceFromApi({
  poolGetResourceMutationName,
  poolId,
  data,
  prefixLength,
  branchName,
}: AllocateResourceFromApiParams) {
  const mutation = jsonToGraphQLQuery({
    mutation: {
      [poolGetResourceMutationName]: {
        __args: {
          data: {
            id: poolId,
            ...(typeof prefixLength === "number" && { prefix_length: prefixLength }),
            data,
          },
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
