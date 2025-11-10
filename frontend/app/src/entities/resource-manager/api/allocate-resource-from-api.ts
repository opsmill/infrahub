import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export interface AllocateResourceFromApiParams extends BranchContextParams {
  poolGetResourceMutationName: string;
  poolId: string;
  data: Record<string, any>;
}

export function allocateResourceFromApi({
  poolGetResourceMutationName,
  poolId,
  data,
  branchName,
}: AllocateResourceFromApiParams) {
  const mutation = jsonToGraphQLQuery({
    mutation: {
      [poolGetResourceMutationName]: {
        __args: {
          data: {
            id: poolId,
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
