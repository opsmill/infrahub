import { ContextParams } from "@/shared/api/types";
import { Filter } from "@/shared/hooks/useFilters";

export interface ObjectKeysBaseParams extends ContextParams {
  objectKind: string;
}

export interface ObjectListKeysParams extends ObjectKeysBaseParams {
  filters?: Filter[];
}

export interface ObjectDetailKeysParams extends ObjectKeysBaseParams {
  objectId: string;
}

export interface ObjectConvertFieldsMappingProps extends ContextParams {
  sourceKind: string;
  targetKind: string;
}

export const objectQueryKeys = {
  all: ["objects"] as const,
  allWithContext: ({ branchName, atDate }: ContextParams) =>
    [...objectQueryKeys.all, branchName, atDate] as const,
  lists: (params: ObjectKeysBaseParams) =>
    [...objectQueryKeys.allWithContext(params), params.objectKind] as const,
  count: (params: ObjectKeysBaseParams) => [...objectQueryKeys.lists(params), "count"] as const,
  list: (params: ObjectListKeysParams) =>
    [...objectQueryKeys.lists(params), params.filters] as const,
  detail: (params: ObjectDetailKeysParams) =>
    [...objectQueryKeys.lists(params), params.objectId] as const,
  ancestors: (params: ObjectDetailKeysParams) =>
    [...objectQueryKeys.detail(params), "ancestors"] as const,
  convert: (params: ObjectConvertFieldsMappingProps) =>
    [
      ...objectQueryKeys.allWithContext(params),
      "fields-mapping-type-conversion",
      params.sourceKind,
      params.targetKind,
    ] as const,
};
