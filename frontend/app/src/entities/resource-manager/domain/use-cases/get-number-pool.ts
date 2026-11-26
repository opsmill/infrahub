import {
  type GetNumberPoolFromApiParams,
  getNumberPoolFromApi,
} from "@/entities/resource-manager/api/get-number-pool-from-api";
import { mapToNumberPoolData } from "@/entities/resource-manager/api/number-pool.mappers";
import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";

export type GetNumberPoolParams = GetNumberPoolFromApiParams;

export const getNumberPool = async (params: GetNumberPoolParams): Promise<NumberPoolData> => {
  const { data, errors } = await getNumberPoolFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const node = data?.CoreNumberPool.edges[0]?.node;
  if (!node) {
    throw new Error("Number pool not found");
  }

  return mapToNumberPoolData(node);
};
