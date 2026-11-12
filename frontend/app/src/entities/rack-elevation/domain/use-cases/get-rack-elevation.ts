import {
  type GetRackElevationFromApiParams,
  getRackElevationFromApi,
} from "@/entities/rack-elevation/api/get-rack-elevation-from-api";
import type { RackElevation } from "@/entities/rack-elevation/domain/model/rack-elevation";

export type GetRackElevationParams = GetRackElevationFromApiParams;
export type GetRackElevationResult = RackElevation;

export const getRackElevation = async (
  params: GetRackElevationParams
): Promise<GetRackElevationResult> => {
  const { data, errors } = await getRackElevationFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data.RackElevation;
};
