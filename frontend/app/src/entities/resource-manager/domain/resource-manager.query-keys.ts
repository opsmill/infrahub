import type { PaginationParams } from "@/shared/api/types";

export interface ResourceUtilizationKeysParams {
  poolId: string;
}

export interface ResourceAllocatedKeysParams extends PaginationParams {
  poolId: string;
  resourceId: string;
}

export interface NumberPoolsKeysParams {
  branchName: string;
  atDate?: Date | null;
  objectKinds: Array<string>;
}

export const resourceManagerQueryKeys = {
  all: ["resource-manager"] as const,
  utilization: (params: ResourceUtilizationKeysParams) =>
    [...resourceManagerQueryKeys.all, "utilization", params.poolId] as const,
  allocated: (params: ResourceAllocatedKeysParams) =>
    [
      ...resourceManagerQueryKeys.all,
      "allocated",
      params.poolId,
      params.resourceId,
      params.limit,
      params.offset,
    ] as const,
  numberPools: (params: NumberPoolsKeysParams) =>
    [
      ...resourceManagerQueryKeys.all,
      "number-pools",
      params.branchName,
      params.atDate,
      params.objectKinds,
    ] as const,
};
