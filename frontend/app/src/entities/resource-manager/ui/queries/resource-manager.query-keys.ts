import type { PaginationParams } from "@/shared/api/types";

export interface ResourceUtilizationKeysParams {
  poolId: string;
}

export interface ResourceAllocatedKeysParams extends PaginationParams {
  poolId: string;
  resourceId: string;
}

export interface NumberPoolKeysParams {
  poolId: string;
  branchName: string;
  atDate?: Date | null;
}

export interface NumberPoolUtilizationKeysParams {
  poolId: string;
  branchName: string;
  atDate?: Date | null;
}

export interface NumberPoolAllocationsKeysParams {
  poolId: string;
  rangeId?: string;
  branchName: string;
  atDate?: Date | null;
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
  numberPool: (params: NumberPoolKeysParams) =>
    [
      ...resourceManagerQueryKeys.all,
      "number-pool",
      params.poolId,
      params.branchName,
      params.atDate,
    ] as const,
  numberPoolUtilization: (params: NumberPoolUtilizationKeysParams) =>
    [
      ...resourceManagerQueryKeys.all,
      "number-pool-utilization",
      params.poolId,
      params.branchName,
      params.atDate,
    ] as const,
  numberPoolAllocations: (params: NumberPoolAllocationsKeysParams) =>
    [
      ...resourceManagerQueryKeys.all,
      "number-pool-allocations",
      params.poolId,
      params.rangeId ?? null,
      params.branchName,
      params.atDate,
    ] as const,
  numberPoolAllocationCount: (params: NumberPoolAllocationsKeysParams) =>
    [
      ...resourceManagerQueryKeys.all,
      "number-pool-allocation-count",
      params.poolId,
      params.rangeId ?? null,
      params.branchName,
      params.atDate,
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
