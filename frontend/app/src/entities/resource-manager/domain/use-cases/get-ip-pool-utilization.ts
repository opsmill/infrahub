import { getIpPoolResourceWeightsFromApi } from "@/entities/resource-manager/api/get-ip-pool-resource-weights-from-api";
import {
  type GetIpPoolUtilizationFromApiParams,
  getIpPoolUtilizationFromApi,
} from "@/entities/resource-manager/api/get-ip-pool-utilization-from-api";
import { mapToIpPoolUtilization } from "@/entities/resource-manager/api/ip-pool-utilization.mappers";
import type { IpPoolUtilization } from "@/entities/resource-manager/domain/model/ip-pool";
import { sortIpPoolResourcesByFillOrder } from "@/entities/resource-manager/domain/rules/sort-ip-pool-resources-by-fill-order";

export interface GetIpPoolUtilizationParams extends GetIpPoolUtilizationFromApiParams {
  weightedKinds: string[];
}

const throwErrors = (errors: ReadonlyArray<{ message: string }> | undefined) => {
  if (errors) throw new Error(errors.map((e) => e.message).join("; "));
};

export type GetIpPoolUtilizationResult = IpPoolUtilization;

type ResourceRef = { id: string; kind: string };

const getWeightsById = async ({
  resources,
  weightedKinds,
  branchName,
  atDate,
}: Omit<GetIpPoolUtilizationParams, "poolId"> & { resources: ResourceRef[] }) => {
  // the server sorts by weight only when every resource prefix kind has one
  const everyKindIsWeighted = resources.every(({ kind }) => weightedKinds.includes(kind));
  if (resources.length === 0 || !everyKindIsWeighted) return new Map<string, number | null>();

  const { data, errors } = await getIpPoolResourceWeightsFromApi({
    resourceIds: resources.map(({ id }) => id),
    // a weighted kind the pool does not use may be missing from the branch's GraphQL schema
    weightedKinds: [...new Set(resources.map(({ kind }) => kind))].sort(),
    branchName,
    atDate,
  });
  throwErrors(errors);

  return new Map(
    (data?.BuiltinIPPrefix.edges ?? []).map(({ node }) => [
      node.id,
      node.allocation_weight?.value ?? null,
    ])
  );
};

export const getIpPoolUtilization = async ({
  poolId,
  weightedKinds,
  branchName,
  atDate,
}: GetIpPoolUtilizationParams): Promise<GetIpPoolUtilizationResult> => {
  const { data, errors } = await getIpPoolUtilizationFromApi({ poolId, branchName, atDate });
  throwErrors(errors);

  const node = data?.InfrahubResourcePoolUtilization;
  if (!node) throw new Error("IP pool utilization not found");

  const weightsById = await getWeightsById({
    resources: node.edges.map(({ node: resource }) => resource),
    weightedKinds,
    branchName,
    atDate,
  });
  const { usage, resources } = mapToIpPoolUtilization(node, weightsById);

  return { usage, resources: sortIpPoolResourcesByFillOrder(resources) };
};
