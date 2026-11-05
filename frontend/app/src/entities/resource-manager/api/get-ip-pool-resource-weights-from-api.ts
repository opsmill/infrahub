import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import type { ContextParams } from "@/shared/api/types";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { ALLOCATION_WEIGHT_ATTRIBUTE } from "@/entities/resource-manager/domain/model/ip-pool";

export interface IpPoolResourceWeightNode {
  id: string;
  allocation_weight?: { value: number | null } | null;
}

interface IpPoolResourceWeightsResult {
  [IP_PREFIX_GENERIC]: { edges: Array<{ node: IpPoolResourceWeightNode }> };
}

export interface GetIpPoolResourceWeightsFromApiParams extends ContextParams {
  resourceIds: string[];
  weightedKinds: string[];
}

// the weight lives on user-defined prefix kinds, so the document is built from the schema
export const buildIpPoolResourceWeightsQuery = ({
  resourceIds,
  weightedKinds,
}: Pick<GetIpPoolResourceWeightsFromApiParams, "resourceIds" | "weightedKinds">) =>
  jsonToGraphQLQuery({
    query: {
      __name: "GET_IP_POOL_RESOURCE_WEIGHTS",
      [IP_PREFIX_GENERIC]: {
        __args: { ids: resourceIds },
        edges: {
          node: {
            id: true,
            __on: weightedKinds.map((kind) => ({
              __typeName: kind,
              [ALLOCATION_WEIGHT_ATTRIBUTE]: { value: true },
            })),
          },
        },
      },
    },
  });

export async function getIpPoolResourceWeightsFromApi({
  resourceIds,
  weightedKinds,
  branchName,
  atDate,
}: GetIpPoolResourceWeightsFromApiParams) {
  const { data, errors } = await graphqlClient.query({
    query: graphql(buildIpPoolResourceWeightsQuery({ resourceIds, weightedKinds })),
    context: { branch: branchName, date: atDate },
  });

  return { data: data as IpPoolResourceWeightsResult | undefined, errors };
}
