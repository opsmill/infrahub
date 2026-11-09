import {
  type GetResourceAllocatedFromApiParams,
  getResourceAllocatedFromApi,
} from "@/entities/resource-manager/api/get-resource-allocated-from-api";

export interface ResourceAllocatedNode {
  id: string;
  display_label: string;
  kind: string;
  branch: string;
  identifier?: string | null;
}

export interface ResourceAllocatedResult {
  nodes: ResourceAllocatedNode[];
  count: number;
}

export type GetResourceAllocatedParams = GetResourceAllocatedFromApiParams;

export type GetResourceAllocated = (
  params: GetResourceAllocatedParams
) => Promise<ResourceAllocatedResult>;

export const getResourceAllocated: GetResourceAllocated = async (params) => {
  const { data, errors } = await getResourceAllocatedFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const allocatedData = data.InfrahubResourcePoolAllocated;

  return {
    nodes: allocatedData.edges.map(({ node }) => node),
    count: allocatedData.count as number,
  };
};
