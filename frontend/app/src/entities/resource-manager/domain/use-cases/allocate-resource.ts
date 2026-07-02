import type { NodeCore } from "@/entities/nodes/types";
import {
  type AllocateResourceFromApiParams,
  allocateResourceFromApi,
} from "@/entities/resource-manager/api/allocate-resource-from-api";

export type AllocateResourceParams = AllocateResourceFromApiParams;

export type AllocateResource = (params: AllocateResourceParams) => Promise<NodeCore>;

export const allocateResource: AllocateResource = async (params) => {
  const { data, errors } = await allocateResourceFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }
  const { node } = data[params.poolGetResourceMutationName];

  return {
    id: node.id,
    display_label: node.display_label,
    __typename: node.kind,
  };
};
