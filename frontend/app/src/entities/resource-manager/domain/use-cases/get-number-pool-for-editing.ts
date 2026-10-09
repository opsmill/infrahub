import {
  type GetNumberPoolForEditingFromApiParams,
  getNumberPoolForEditingFromApi,
} from "@/entities/resource-manager/api/get-number-pool-for-editing-from-api";
import { toNumberPoolForEditing } from "@/entities/resource-manager/api/number-pool.mappers";
import type { NumberPoolForEditing } from "@/entities/resource-manager/domain/model/number-pool";

export type GetNumberPoolForEditingParams = GetNumberPoolForEditingFromApiParams;

export type GetNumberPoolForEditingResult = NumberPoolForEditing;

export type GetNumberPoolForEditing = (
  params: GetNumberPoolForEditingParams
) => Promise<GetNumberPoolForEditingResult>;

export const getNumberPoolForEditing: GetNumberPoolForEditing = async (params) => {
  const { data } = await getNumberPoolForEditingFromApi(params);
  const node = data.CoreNumberPool.edges[0]?.node;

  if (!node) {
    throw new Error(`Number pool ${params.poolId} not found`);
  }

  return toNumberPoolForEditing(node);
};
