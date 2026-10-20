import {
  type GetNumberPoolDivisionsFromApiParams,
  getNumberPoolDivisionsFromApi,
} from "@/entities/resource-manager/api/get-number-pool-divisions-from-api";
import { mapToNumberPoolDivisions } from "@/entities/resource-manager/api/number-pool-division.mappers";
import type { NumberPoolDivisions } from "@/entities/resource-manager/domain/model/number-pool";

export type GetNumberPoolDivisionsParams = GetNumberPoolDivisionsFromApiParams;

export const getNumberPoolDivisions = async (
  params: GetNumberPoolDivisionsParams
): Promise<NumberPoolDivisions> => {
  const { data, errors } = await getNumberPoolDivisionsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return mapToNumberPoolDivisions(data.InfrahubNumberPoolDivisions);
};
